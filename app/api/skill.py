from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.security import require_api_key
from app.schemas import SkillExecuteRequest, SkillExecuteResponse
from app.skill.actions import ACTION_CATALOG, execute_action

router = APIRouter(prefix="/skill", tags=["skill"], dependencies=[Depends(require_api_key)])


@router.get("/manifest")
def skill_manifest() -> dict:
    settings = get_settings()
    return {
        "name": "adamhub-life-skill",
        "version": "0.1.0",
        "description": "Skill API for life management domains on AdamHUB",
        "base_url": settings.public_base_url,
        "auth": {"type": "api_key", "header": "X-API-Key"},
        "actions": ACTION_CATALOG,
    }


@router.post("/execute", response_model=SkillExecuteResponse)
def skill_execute(payload: SkillExecuteRequest, session: SessionDep) -> SkillExecuteResponse:
    try:
        data = execute_action(payload.action, payload.input, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SkillExecuteResponse(action=payload.action, ok=True, data=data)
