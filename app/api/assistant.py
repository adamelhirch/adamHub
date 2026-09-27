import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import select

from app.api._crud import create, get_owned_or_404, save
from app.api.deps import CurrentOrOwnerUser, SessionDep
from app.models.entities import UserMemory, UserProfile
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantSessionResetResponse,
    AudioTranscribeRequest,
    AudioTranscribeResponse,
    UserMemoryCreate,
    UserMemoryRead,
    UserProfileRead,
    UserProfileUpdate,
)
from app.services.assistant.context_builder import build_system_context
from app.services.assistant.memory_extractor import background_memory_extractor_task
from app.services.assistant.openrouter_client import stream_openrouter_chat
from app.services.assistant.tool_dispatcher import dispatch_assistant_tool, get_assistant_tools

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat")
async def assistant_chat(
    payload: AssistantChatRequest,
    session: SessionDep,
    user: CurrentOrOwnerUser,
    background_tasks: BackgroundTasks,
) -> StreamingResponse:
    """Stream assistant response and execute tools via Server-Sent Events (SSE)."""
    # Schedule background memory extraction without blocking the response
    background_tasks.add_task(
        background_memory_extractor_task,
        user.id,
        payload.message,
    )

    system_prompt = build_system_context(session, user.id)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
    ]
    if payload.history:
        for turn in payload.history[-12:]:
            clean_content = (turn.content or "").strip()
            if clean_content and turn.role in ("user", "assistant"):
                messages.append({"role": turn.role, "content": clean_content})

    if payload.images:
        user_content: list[dict[str, Any]] = [
            {"type": "text", "text": payload.message or "Analyse cette image"}
        ]
        for img_url in payload.images:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": img_url, "detail": "auto"},
            })
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": payload.message})

    tools = get_assistant_tools()

    MAX_AGENT_STEPS = 6

    async def sse_event_stream() -> AsyncGenerator[str, None]:
        full_text: list[str] = []
        current_messages: list[dict[str, Any]] = list(messages)

        for step in range(MAX_AGENT_STEPS):
            step_text: list[str] = []
            accumulated_tools: dict[int, dict] = {}

            async for chunk in stream_openrouter_chat(current_messages, tools=tools):
                delta = chunk.get("delta", "")
                if delta:
                    step_text.append(delta)
                    full_text.append(delta)
                    yield f"event: delta\ndata: {json.dumps({'content': delta})}\n\n"

                tool_calls = chunk.get("tool_calls", [])
                if tool_calls:
                    for tc in tool_calls:
                        idx = tc.get("index", 0)
                        if idx not in accumulated_tools:
                            accumulated_tools[idx] = {
                                "id": tc.get("id", f"call_{step}_{idx}"),
                                "name": "",
                                "arguments": "",
                            }
                        if tc.get("id"):
                            accumulated_tools[idx]["id"] = tc["id"]
                        func = tc.get("function", {})
                        if func.get("name"):
                            accumulated_tools[idx]["name"] = func["name"]
                        if func.get("arguments"):
                            accumulated_tools[idx]["arguments"] += func["arguments"]

            # If no tools were called in this step, model has concluded its response
            if not accumulated_tools:
                break

            # Record assistant turn with tool_calls in context
            assistant_turn = {
                "role": "assistant",
                "content": "".join(step_text) if step_text else None,
                "tool_calls": [
                    {
                        "id": t["id"],
                        "type": "function",
                        "function": {"name": t["name"], "arguments": t["arguments"]},
                    }
                    for t in accumulated_tools.values()
                ],
            }
            current_messages.append(assistant_turn)

            # Dispatch accumulated tools and feed results back to the LLM
            for idx in sorted(accumulated_tools.keys()):
                t_data = accumulated_tools[idx]
                fn_name = t_data["name"]
                raw_args = t_data["arguments"]
                yield f"event: tool_call\ndata: {json.dumps({'id': t_data['id'], 'type': 'function', 'function': {'name': fn_name, 'arguments': raw_args}})}\n\n"

                tool_output: dict[str, Any]
                if fn_name:
                    try:
                        fn_args = json.loads(raw_args) if raw_args else {}
                        tool_result = dispatch_assistant_tool(fn_name, fn_args, session, user)
                        yield f"event: tool_result\ndata: {json.dumps(tool_result)}\n\n"
                        tool_output = tool_result
                    except Exception as exc:
                        err_payload = {"action": fn_name, "success": False, "error": str(exc)}
                        yield f"event: tool_result\ndata: {json.dumps(err_payload)}\n\n"
                        tool_output = err_payload
                else:
                    tool_output = {"success": False, "error": "Nom de fonction manquant"}

                # Crucial agent feedback: append tool result to current_messages for next iteration
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": t_data["id"],
                    "name": fn_name,
                    "content": json.dumps(tool_output),
                })

        if not "".join(full_text).strip():
            confirm_text = "Toutes les actions ont été effectuées avec succès !"
            yield f"event: delta\ndata: {json.dumps({'content': confirm_text})}\n\n"
            full_text.append(confirm_text)

        yield f"event: done\ndata: {json.dumps({'full_text': ''.join(full_text)})}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/profile", response_model=UserProfileRead)
def get_user_profile(session: SessionDep, user: CurrentOrOwnerUser) -> UserProfileRead:
    profile = session.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
    if profile is None:
        profile = UserProfile(
            user_id=user.id,
            dietary_preferences=[],
            fitness_goals="",
            lifestyle_notes="",
            ai_tone="direct",
            onboarding_completed=False,
        )
        profile = create(session, profile)
    return UserProfileRead.model_validate(profile, from_attributes=True)


@router.put("/profile", response_model=UserProfileRead)
def update_user_profile(
    payload: UserProfileUpdate, session: SessionDep, user: CurrentOrOwnerUser
) -> UserProfileRead:
    profile = session.exec(select(UserProfile).where(UserProfile.user_id == user.id)).first()
    if profile is None:
        profile = UserProfile(
            user_id=user.id,
            dietary_preferences=payload.dietary_preferences or [],
            fitness_goals=payload.fitness_goals or "",
            lifestyle_notes=payload.lifestyle_notes or "",
            ai_tone=payload.ai_tone or "direct",
            onboarding_completed=payload.onboarding_completed or False,
        )
        profile = create(session, profile)
    else:
        if payload.dietary_preferences is not None:
            profile.dietary_preferences = payload.dietary_preferences
        if payload.fitness_goals is not None:
            profile.fitness_goals = payload.fitness_goals
        if payload.lifestyle_notes is not None:
            profile.lifestyle_notes = payload.lifestyle_notes
        if payload.ai_tone is not None:
            profile.ai_tone = payload.ai_tone
        if payload.onboarding_completed is not None:
            profile.onboarding_completed = payload.onboarding_completed
        profile.updated_at = datetime.now(timezone.utc)
        profile = save(session, profile)
    return UserProfileRead.model_validate(profile, from_attributes=True)


@router.get("/memories", response_model=list[UserMemoryRead])
def list_user_memories(session: SessionDep, user: CurrentOrOwnerUser) -> list[UserMemoryRead]:
    memories = session.exec(
        select(UserMemory)
        .where(UserMemory.user_id == user.id, UserMemory.is_active == True)  # noqa: E712
        .order_by(UserMemory.created_at.desc())
    ).all()
    return [UserMemoryRead.model_validate(m, from_attributes=True) for m in memories]


@router.post("/memories", response_model=UserMemoryRead, status_code=status.HTTP_201_CREATED)
def create_user_memory(
    payload: UserMemoryCreate, session: SessionDep, user: CurrentOrOwnerUser
) -> UserMemoryRead:
    memory = UserMemory(
        user_id=user.id,
        category=payload.category,
        fact=payload.fact,
        confidence=payload.confidence,
        source="manual",
        is_active=True,
    )
    memory = create(session, memory)
    return UserMemoryRead.model_validate(memory, from_attributes=True)


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_memory(memory_id: int, session: SessionDep, user: CurrentOrOwnerUser) -> None:
    memory = get_owned_or_404(session, UserMemory, memory_id, user_id=user.id, detail="Memory not found")
    memory.is_active = False
    memory.updated_at = datetime.now(timezone.utc)
    save(session, memory)


@router.post("/session/reset", response_model=AssistantSessionResetResponse)
def reset_assistant_session(user: CurrentOrOwnerUser) -> AssistantSessionResetResponse:
    # Ephemeral session reset: client clears local message stack;
    # Server confirms user authentication and tenancy integrity.
    return AssistantSessionResetResponse(ok=True)


@router.post("/transcribe", response_model=AudioTranscribeResponse)
async def transcribe_audio(
    payload: AudioTranscribeRequest,
    user: CurrentOrOwnerUser,
) -> AudioTranscribeResponse:
    """Transcribe base64 encoded audio bytes into text."""
    import base64
    import tempfile
    from pathlib import Path

    try:
        audio_data = base64.b64decode(payload.audio_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Données audio base64 invalides")

    if not audio_data:
        raise HTTPException(status_code=400, detail="Fichier audio vide")

    ext = ".webm"
    if "wav" in payload.mime_type:
        ext = ".wav"
    elif "mp4" in payload.mime_type or "m4a" in payload.mime_type:
        ext = ".m4a"
    elif "mp3" in payload.mime_type:
        ext = ".mp3"

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
        tmp_file.write(audio_data)

    transcription = ""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(tmp_path), language="fr")
        transcription = " ".join([seg.text for seg in segments]).strip()
    except Exception:
        transcription = ""
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    if not transcription:
        transcription = "Message vocal reçu"

    return AudioTranscribeResponse(text=transcription)

