from fastapi import APIRouter, Depends

from app.core.security import require_api_key

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/check", dependencies=[Depends(require_api_key)])
def auth_check() -> dict:
    return {"ok": True}
