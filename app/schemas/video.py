from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class VideoSourceRequest(BaseModel):
    url: str


class TranscriptSegmentRead(BaseModel):
    start: float | None = None
    duration: float | None = None
    text: str


class VideoSourceRead(BaseModel):
    url: str
    canonical_url: str | None = None
    platform: str
    title: str | None = None
    description: str | None = None
    transcript: str | None = None
    transcript_source: str | None = None
    transcript_segments: list[TranscriptSegmentRead] = Field(default_factory=list)
    author: str | None = None
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    duration_seconds: int | None = None
    warnings: list[str] = Field(default_factory=list)
