from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from app.models import TaskPriority, TaskScheduleMode, TaskStatus
from app.schemas._schedule import SCHEDULE_TIME_PATTERN


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    subtasks: list["TaskSubtask"] = Field(default_factory=list)
    schedule_mode: TaskScheduleMode | None = None
    schedule_time: str | None = Field(default=None, pattern=SCHEDULE_TIME_PATTERN)
    schedule_weekday: int | None = Field(default=None, ge=0, le=6)
    due_at: datetime | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_minutes: int | None = None
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_schedule(self) -> "TaskCreate":
        self.subtasks = _normalize_task_subtasks(self.subtasks)

        if self.schedule_mode is None:
            self.schedule_mode = (
                TaskScheduleMode.ONCE if self.due_at is not None else TaskScheduleMode.NONE
            )

        if self.schedule_mode == TaskScheduleMode.NONE:
            self.due_at = None
            self.schedule_time = None
            self.schedule_weekday = None
        elif self.schedule_mode == TaskScheduleMode.ONCE:
            if self.due_at is None:
                raise ValueError("due_at is required when schedule_mode is once")
            self.schedule_time = None
            self.schedule_weekday = None
        elif self.schedule_mode == TaskScheduleMode.DAILY:
            if not self.schedule_time:
                raise ValueError("schedule_time is required when schedule_mode is daily")
            self.due_at = None
            self.schedule_weekday = None
        elif self.schedule_mode == TaskScheduleMode.WEEKLY:
            if not self.schedule_time:
                raise ValueError("schedule_time is required when schedule_mode is weekly")
            if self.schedule_weekday is None:
                raise ValueError("schedule_weekday is required when schedule_mode is weekly")
            self.due_at = None

        return self


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    subtasks: list["TaskSubtask"] | None = None
    schedule_mode: TaskScheduleMode | None = None
    schedule_time: str | None = Field(default=None, pattern=SCHEDULE_TIME_PATTERN)
    schedule_weekday: int | None = Field(default=None, ge=0, le=6)
    due_at: datetime | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    estimated_minutes: int | None = None
    tags: list[str] | None = None

    @model_validator(mode="after")
    def normalize_subtasks(self) -> "TaskUpdate":
        if self.subtasks is not None:
            self.subtasks = _normalize_task_subtasks(self.subtasks)
        return self


class TaskRead(BaseModel):
    id: int
    title: str
    description: str | None
    subtasks: list["TaskSubtask"] = Field(default_factory=list)
    status: TaskStatus
    priority: TaskPriority
    schedule_mode: TaskScheduleMode
    schedule_time: str | None
    schedule_weekday: int | None
    due_at: datetime | None
    estimated_minutes: int | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class TaskSubtask(BaseModel):
    id: str | None = None
    title: str
    completed: bool = False


def _normalize_task_subtasks(subtasks: list["TaskSubtask"] | None) -> list["TaskSubtask"]:
    normalized: list[TaskSubtask] = []
    for subtask in subtasks or []:
        title = subtask.title.strip()
        if not title:
            continue
        normalized.append(
            TaskSubtask(
                id=(subtask.id or uuid4().hex),
                title=title,
                completed=subtask.completed,
            )
        )
    return normalized
