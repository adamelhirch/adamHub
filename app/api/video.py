from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentOrOwnerUser
from app.schemas import VideoSourceRead, VideoSourceRequest
from app.services.video_intake import extract_video_source

router = APIRouter(prefix="/video", tags=["video"])


@router.post("/extract", response_model=VideoSourceRead)
def extract_video_source_endpoint(payload: VideoSourceRequest, user: CurrentOrOwnerUser) -> VideoSourceRead:  # noqa: ARG001
    try:
        return extract_video_source(payload.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
