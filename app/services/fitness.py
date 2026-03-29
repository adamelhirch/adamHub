from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean

from sqlmodel import Session, select

from app.models import FitnessExerciseMode, FitnessMeasurement, FitnessSession, FitnessSessionStatus, FitnessSessionType
from app.schemas import (
    FitnessExerciseIn,
    FitnessExerciseRead,
    FitnessMeasurementRead,
    FitnessOverviewRead,
    FitnessSessionRead,
    FitnessStatsRead,
)


def _ensure_utc(value: datetime | None) -> datetime:
    if value is None:
        value = datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_fitness_exercise(raw: object) -> FitnessExerciseRead | None:
    if isinstance(raw, str):
        name = raw.strip()
        if not name:
            return None
        return FitnessExerciseRead(name=name, mode=FitnessExerciseMode.REPS)

    if isinstance(raw, FitnessExerciseIn):
        payload = raw.model_dump()
        payload["name"] = raw.name.strip()
        if not payload["name"]:
            return None
        return FitnessExerciseRead(**payload)

    if isinstance(raw, dict):
        name = str(raw.get("name", "")).strip()
        if not name:
            return None
        mode_value = raw.get("mode") or raw.get("kind") or FitnessExerciseMode.REPS
        try:
            mode = FitnessExerciseMode(mode_value)
        except ValueError:
            mode = FitnessExerciseMode.REPS

        reps = raw.get("reps")
        duration_minutes = raw.get("duration_minutes")
        note = raw.get("note")
        return FitnessExerciseRead(
            name=name,
            mode=mode,
            reps=int(reps) if reps is not None else None,
            duration_minutes=int(duration_minutes) if duration_minutes is not None else None,
            note=str(note).strip() if isinstance(note, str) and note.strip() else None,
        )

    return None


def _normalize_fitness_exercises(values: list[object] | None) -> list[FitnessExerciseRead]:
    normalized: list[FitnessExerciseRead] = []
    for value in values or []:
        exercise = _normalize_fitness_exercise(value)
        if exercise is not None:
            normalized.append(exercise)
    return normalized


def coerce_fitness_exercises(values: list[object] | None) -> list[dict[str, object]]:
    return [exercise.model_dump(mode="json") for exercise in _normalize_fitness_exercises(values)]


def build_fitness_session_read(row: FitnessSession) -> FitnessSessionRead:
    return FitnessSessionRead(
        id=row.id,
        title=row.title,
        session_type=row.session_type,
        planned_at=row.planned_at,
        duration_minutes=row.duration_minutes,
        exercises=_normalize_fitness_exercises(row.exercises),
        note=row.note,
        status=row.status,
        completed_at=row.completed_at,
        actual_duration_minutes=row.actual_duration_minutes,
        effort_rating=row.effort_rating,
        calories_burned=row.calories_burned,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def build_fitness_measurement_read(row: FitnessMeasurement) -> FitnessMeasurementRead:
    return FitnessMeasurementRead(
        id=row.id,
        recorded_at=row.recorded_at,
        body_weight_kg=row.body_weight_kg,
        body_fat_pct=row.body_fat_pct,
        resting_hr=row.resting_hr,
        sleep_hours=row.sleep_hours,
        steps=row.steps,
        note=row.note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def build_fitness_overview(session: Session) -> FitnessOverviewRead:
    now = datetime.now(timezone.utc)
    sessions = session.exec(select(FitnessSession).order_by(FitnessSession.planned_at.desc())).all()
    measurements = session.exec(select(FitnessMeasurement).order_by(FitnessMeasurement.recorded_at.desc())).all()

    planned_sessions = [row for row in sessions if row.status != FitnessSessionStatus.SKIPPED]
    upcoming_sessions = [
        row
        for row in sessions
        if row.status == FitnessSessionStatus.PLANNED and _ensure_utc(row.planned_at) >= now
    ]
    recent_sessions = sessions[:10]

    since_30d = now - timedelta(days=30)
    sessions_30d = [
        row for row in sessions if _ensure_utc(row.planned_at) >= since_30d and row.status != FitnessSessionStatus.SKIPPED
    ]
    completed_30d = [row for row in sessions_30d if row.status == FitnessSessionStatus.COMPLETED]
    completion_rate = round((len(completed_30d) / len(sessions_30d)) * 100, 1) if sessions_30d else 0.0

    completed_durations = [
        row.actual_duration_minutes or row.duration_minutes
        for row in sessions
        if row.status == FitnessSessionStatus.COMPLETED or row.completed_at is not None
    ]
    avg_duration = round(mean(completed_durations), 1) if completed_durations else None

    latest_measurement = next((row for row in measurements if row.body_weight_kg is not None
                              or row.body_fat_pct is not None
                              or row.resting_hr is not None
                              or row.sleep_hours is not None), None)
    body_weight_delta = None
    if latest_measurement and latest_measurement.body_weight_kg is not None:
        cutoff = _ensure_utc(latest_measurement.recorded_at) - timedelta(days=30)
        candidates = [
            row
            for row in measurements
            if row.body_weight_kg is not None and _ensure_utc(row.recorded_at) <= cutoff
        ]
        if candidates:
            baseline = max(candidates, key=lambda row: _ensure_utc(row.recorded_at))
            body_weight_delta = round(latest_measurement.body_weight_kg - baseline.body_weight_kg, 1)

    latest_resting_hr = latest_measurement.resting_hr if latest_measurement else None
    latest_sleep_hours = latest_measurement.sleep_hours if latest_measurement else None
    latest_body_weight = latest_measurement.body_weight_kg if latest_measurement else None

    return FitnessOverviewRead(
        stats=FitnessStatsRead(
            planned_sessions=len(planned_sessions),
            upcoming_sessions=len(upcoming_sessions),
            completed_sessions_30d=len(completed_30d),
            completion_rate_30d=completion_rate,
            avg_duration_minutes=avg_duration,
            latest_body_weight_kg=latest_body_weight,
            body_weight_delta_30d=body_weight_delta,
            latest_resting_hr=latest_resting_hr,
            latest_sleep_hours=latest_sleep_hours,
        ),
        upcoming_sessions=[build_fitness_session_read(row) for row in upcoming_sessions],
        recent_sessions=[build_fitness_session_read(row) for row in recent_sessions],
        measurements=[build_fitness_measurement_read(row) for row in measurements[:12]],
    )
