from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import SessionDep, owner_only_user
from app.core.auth import resolve_current_or_owner_user
from app.core.config import get_settings
from app.schemas import SkillExecuteRequest, SkillExecuteResponse
from app.skill.actions import action_catalog_manifest, execute_action

router = APIRouter(prefix="/skill", tags=["skill"], dependencies=[Depends(owner_only_user)])


@router.get("/manifest")
def skill_manifest() -> dict:
    settings = get_settings()
    return {
        "name": "adamhub-life-skill",
        "version": "0.2.0",
        "description": "Skill API for life management domains on AdamHUB",
        "base_url": settings.public_base_url,
        "auth": {"type": "api_key", "header": "X-API-Key"},
        "actions": action_catalog_manifest(),
        "workflows": {},
    }


@router.post("/execute", response_model=SkillExecuteResponse)
def skill_execute(
    payload: SkillExecuteRequest, session: SessionDep, request: Request
) -> SkillExecuteResponse:
    # The router-level require_owner_only already authenticated the caller (owner
    # via X-API-Key or owner JWT); resolve the acting user with the same dual-mode
    # logic used by the domain routers so skill actions are scoped to the same
    # tenant the HTTP calls are.
    user = resolve_current_or_owner_user(request, session)
    try:
        data = execute_action(payload.action, payload.input, session, user=user)
    except (ValueError, TypeError, KeyError) as exc:
        # ValueError is the skill layer's contract for actionable failures;
        # TypeError/KeyError are also converted here so no residual parsing
        # bug in a skill handler can leak a raw 500 to the assistant.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SkillExecuteResponse(action=payload.action, ok=True, data=data)
