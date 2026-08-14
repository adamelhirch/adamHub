from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class LinearProjectRead(BaseModel):
    id: str
    name: str
    key: str | None = None
    state: str | None = None
    description: str | None = None
    url: str | None = None


class LinearIssueRead(BaseModel):
    id: str
    identifier: str | None = None
    title: str
    state: str | None = None
    priority: int | None = None
    due_date: date | None = None
    assignee_name: str | None = None
    project_id: str | None = None
    url: str | None = None


class LinearIssueCreate(BaseModel):
    title: str
    description: str | None = None
    project_id: str | None = None
    team_id: str | None = None
    priority: int | None = Field(default=None, ge=0, le=4)
    assignee_id: str | None = None
    due_date: date | None = None


class LinearSyncResult(BaseModel):
    projects: int
    issues: int
    synced_at: datetime
