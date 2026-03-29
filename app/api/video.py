from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.schemas import VideoSourceRead, VideoSourceRequest
from app.services.video_intake import extract_video_source

router = APIRouter(prefix="/video", tags=["video"], dependencies=[Depends(require_api_key)])


@router.post("/extract", response_model=VideoSourceRead)
def extract_video_source_endpoint(payload: VideoSourceRequest, session: SessionDep) -> VideoSourceRead:  # noqa: ARG001
    try:
        return extract_video_source(payload.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
