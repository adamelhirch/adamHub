from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import NoteKind


class NoteCreate(BaseModel):
    title: str
    content: str
    kind: NoteKind = NoteKind.NOTE
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    mood: int | None = Field(default=None, ge=1, le=10)


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    kind: NoteKind | None = None
    tags: list[str] | None = None
    pinned: bool | None = None
    mood: int | None = Field(default=None, ge=1, le=10)


class NoteRead(BaseModel):
    id: int
    title: str
    content: str
    kind: NoteKind
    tags: list[str]
    pinned: bool
    mood: int | None
    created_at: datetime
    updated_at: datetime
