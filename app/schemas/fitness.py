from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models import (
    FitnessExerciseMode,
    FitnessSessionStatus,
    FitnessSessionType,
)


class FitnessExerciseIn(BaseModel):
    name: str
    mode: FitnessExerciseMode = FitnessExerciseMode.REPS
    reps: int | None = Field(default=None, ge=1, le=1000)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    note: str | None = None

    @model_validator(mode="after")
    def validate_tracking_value(self) -> "FitnessExerciseIn":
        if self.mode == FitnessExerciseMode.REPS:
            if self.reps is None or self.duration_minutes is not None:
                raise ValueError("reps is required when mode is reps")
        if self.mode == FitnessExerciseMode.DURATION:
            if self.duration_minutes is None or self.reps is not None:
                raise ValueError("duration_minutes is required when mode is duration")
        return self


class FitnessExerciseRead(BaseModel):
    name: str
    mode: FitnessExerciseMode
    reps: int | None = None
    duration_minutes: int | None = None
    note: str | None = None


class FitnessSessionCreate(BaseModel):
    title: str
    session_type: FitnessSessionType = FitnessSessionType.MIXED
    planned_at: datetime | None = None
    duration_minutes: int = Field(default=45, ge=1, le=600)
    exercises: list[FitnessExerciseIn | str] = Field(default_factory=list)
    note: str | None = None


class FitnessSessionUpdate(BaseModel):
    title: str | None = None
    session_type: FitnessSessionType | None = None
    planned_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    exercises: list[FitnessExerciseIn | str] | None = None
    note: str | None = None
    status: FitnessSessionStatus | None = None
    actual_duration_minutes: int | None = Field(default=None, ge=1, le=600)
    effort_rating: int | None = Field(default=None, ge=1, le=10)
    calories_burned: float | None = None


class FitnessSessionComplete(BaseModel):
    note: str | None = None
    actual_duration_minutes: int | None = Field(default=None, ge=1, le=600)
    effort_rating: int | None = Field(default=None, ge=1, le=10)
    calories_burned: float | None = None


class FitnessSessionRead(BaseModel):
    id: int
    title: str
    session_type: FitnessSessionType
    planned_at: datetime
    duration_minutes: int
    exercises: list[FitnessExerciseRead]
    note: str | None
    status: FitnessSessionStatus
    completed_at: datetime | None
    actual_duration_minutes: int | None
    effort_rating: int | None
    calories_burned: float | None
    created_at: datetime
    updated_at: datetime


class FitnessMeasurementCreate(BaseModel):
    recorded_at: datetime | None = None
    body_weight_kg: float | None = Field(default=None, ge=0, le=1000)
    body_fat_pct: float | None = Field(default=None, ge=0, le=100)
    resting_hr: int | None = Field(default=None, ge=20, le=220)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    steps: int | None = Field(default=None, ge=0)
    note: str | None = None


class FitnessMeasurementUpdate(BaseModel):
    recorded_at: datetime | None = None
    body_weight_kg: float | None = Field(default=None, ge=0, le=1000)
    body_fat_pct: float | None = Field(default=None, ge=0, le=100)
    resting_hr: int | None = Field(default=None, ge=20, le=220)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    steps: int | None = Field(default=None, ge=0)
    note: str | None = None


class FitnessMeasurementRead(BaseModel):
    id: int
    recorded_at: datetime
    body_weight_kg: float | None
    body_fat_pct: float | None
    resting_hr: int | None
    sleep_hours: float | None
    steps: int | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class FitnessStatsRead(BaseModel):
    planned_sessions: int
    upcoming_sessions: int
    completed_sessions_30d: int
    completion_rate_30d: float
    avg_duration_minutes: float | None
    latest_body_weight_kg: float | None
    body_weight_delta_30d: float | None
    latest_resting_hr: int | None
    latest_sleep_hours: float | None


class FitnessOverviewRead(BaseModel):
    stats: FitnessStatsRead
    upcoming_sessions: list[FitnessSessionRead]
    recent_sessions: list[FitnessSessionRead]
    measurements: list[FitnessMeasurementRead]
