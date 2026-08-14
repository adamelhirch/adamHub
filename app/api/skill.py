from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import SessionDep
from app.core.auth import resolve_current_or_owner_user
from app.core.config import get_settings
from app.core.security import require_api_key
from app.schemas import SkillExecuteRequest, SkillExecuteResponse
from app.skill.actions import action_catalog_manifest, execute_action

router = APIRouter(prefix="/skill", tags=["skill"], dependencies=[Depends(require_api_key)])


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
        "workflows": {
            "ubereats_grocery": (
                "End-to-end Uber Eats grocery skill. SETUP (once): ubereats.geocode_address → "
                "ubereats.save_address (activate=true) → ubereats.list_stores → "
                "ubereats.set_selected_store. DAILY USE: ubereats.search_products(query, sort_by) "
                "→ ubereats.add_to_cart(cache_id) (also mirrors to grocery list). "
                "AFTER DELIVERY: ubereats.import_order_to_pantry(tracking_url) for the user's own "
                "orders. THIRD-PARTY ORDERS (friend ordered for the user): the API can't read those "
                "items — ASK the user to share screenshots of the tracking page, EXTRACT items via "
                "your vision capability, then call ubereats.import_third_party_order with the "
                "parsed list. MANUAL EDITS: pantry.update_item / pantry.consume_item / "
                "pantry.delete_item / grocery.* — let the user fine-tune anything."
            ),
        },
    }


@router.post("/execute", response_model=SkillExecuteResponse)
def skill_execute(
    payload: SkillExecuteRequest, session: SessionDep, request: Request
) -> SkillExecuteResponse:
    # The router-level require_api_key already authenticated the caller; resolve
    # the acting user with the same dual-mode logic used by the domain routers so
    # skill actions are scoped to the same tenant the HTTP calls are.
    user = resolve_current_or_owner_user(request, session)
    try:
        data = execute_action(payload.action, payload.input, session, user=user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return SkillExecuteResponse(action=payload.action, ok=True, data=data)
