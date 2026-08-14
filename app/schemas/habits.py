from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models import HabitFrequency
from app.schemas._schedule import (
    SCHEDULE_TIME_PATTERN,
    _normalize_schedule_times,
    _normalize_schedule_weekdays,
)


class HabitCreate(BaseModel):
    name: str
    description: str | None = None
    frequency: HabitFrequency = HabitFrequency.DAILY
    target_per_period: int = 1
    schedule_time: str | None = Field(default=None, pattern=SCHEDULE_TIME_PATTERN)
    schedule_times: list[str] = Field(default_factory=list)
    schedule_weekday: int | None = Field(default=None, ge=0, le=6)
    schedule_weekdays: list[int] = Field(default_factory=list)
    duration_minutes: int = Field(default=30, ge=1, le=1440)

    @model_validator(mode="after")
    def validate_schedule(self) -> "HabitCreate":
        self.schedule_time, self.schedule_times = _normalize_schedule_times(
            self.schedule_time,
            self.schedule_times,
        )
        self.schedule_weekday, self.schedule_weekdays = _normalize_schedule_weekdays(
            self.schedule_weekday,
            self.schedule_weekdays,
        )

        if self.schedule_time is None:
            self.schedule_weekday = None
            self.schedule_weekdays = []
            return self

        if self.frequency == HabitFrequency.WEEKLY and self.schedule_weekday is None:
            raise ValueError("schedule_weekday is required for weekly habits scheduled in the calendar")

        if self.frequency == HabitFrequency.DAILY:
            self.schedule_weekday = None
            self.schedule_weekdays = []

        return self


class HabitRead(BaseModel):
    id: int
    name: str
    description: str | None
    frequency: HabitFrequency
    target_per_period: int
    schedule_time: str | None
    schedule_times: list[str] = Field(default_factory=list)
    schedule_weekday: int | None
    schedule_weekdays: list[int] = Field(default_factory=list)
    duration_minutes: int
    streak: int
    active: bool
    created_at: datetime
    updated_at: datetime


class HabitUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    frequency: HabitFrequency | None = None
    target_per_period: int | None = Field(default=None, ge=1, le=365)
    schedule_time: str | None = Field(default=None, pattern=SCHEDULE_TIME_PATTERN)
    schedule_times: list[str] | None = None
    schedule_weekday: int | None = Field(default=None, ge=0, le=6)
    schedule_weekdays: list[int] | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    active: bool | None = None


class HabitLogCreate(BaseModel):
    value: int = 1
    note: str | None = None


class HabitLogRead(BaseModel):
    id: int
    habit_id: int
    logged_at: datetime
    value: int
    note: str | None
