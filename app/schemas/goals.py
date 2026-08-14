from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import GoalStatus


class GoalCreate(BaseModel):
    title: str
    description: str | None = None
    status: GoalStatus = GoalStatus.PLANNED
    progress_percent: int = Field(default=0, ge=0, le=100)
    target_date: date | None = None
    tags: list[str] = Field(default_factory=list)


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: GoalStatus | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    target_date: date | None = None
    tags: list[str] | None = None


class GoalRead(BaseModel):
    id: int
    title: str
    description: str | None
    status: GoalStatus
    progress_percent: int
    target_date: date | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class GoalMilestoneCreate(BaseModel):
    title: str
    due_at: datetime | None = None


class GoalMilestoneUpdate(BaseModel):
    title: str | None = None
    due_at: datetime | None = None
    completed: bool | None = None


class GoalMilestoneRead(BaseModel):
    id: int
    goal_id: int
    title: str
    due_at: datetime | None
    completed: bool
    completed_at: datetime | None
    created_at: datetime
