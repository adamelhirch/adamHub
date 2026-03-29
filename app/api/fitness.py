from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import CalendarSource, FitnessMeasurement, FitnessSession, FitnessSessionStatus
from app.schemas import (
    FitnessExerciseIn,
    FitnessMeasurementCreate,
    FitnessMeasurementRead,
    FitnessMeasurementUpdate,
    FitnessOverviewRead,
    FitnessSessionComplete,
    FitnessSessionCreate,
    FitnessSessionRead,
    FitnessSessionUpdate,
)
from app.services.fitness import (
    _ensure_utc,
    coerce_fitness_exercises,
    build_fitness_measurement_read,
    build_fitness_overview,
    build_fitness_session_read,
)
from app.services.calendar_hub import validate_calendar_slot_free

router = APIRouter(prefix="/fitness", tags=["fitness"], dependencies=[Depends(require_api_key)])


def _normalize_exercise_payload(values: list[FitnessExerciseIn | str] | None) -> list[dict[str, object]]:
    return coerce_fitness_exercises(values)


@router.get("", response_model=FitnessOverviewRead)
def get_fitness_overview(session: SessionDep) -> FitnessOverviewRead:
    return build_fitness_overview(session)


@router.get("/sessions", response_model=list[FitnessSessionRead])
def list_fitness_sessions(
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=300),
) -> list[FitnessSessionRead]:
    rows = session.exec(select(FitnessSession).order_by(FitnessSession.planned_at.desc()).limit(limit)).all()
    return [build_fitness_session_read(row) for row in rows]


@router.post("/sessions", response_model=FitnessSessionRead)
def create_fitness_session(payload: FitnessSessionCreate, session: SessionDep) -> FitnessSessionRead:
    planned_at = _ensure_utc(payload.planned_at)
    try:
        validate_calendar_slot_free(
            session,
            planned_at,
            planned_at + timedelta(minutes=payload.duration_minutes),
            source=CalendarSource.FITNESS_SESSION,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    row = FitnessSession(
        title=payload.title.strip(),
        session_type=payload.session_type,
        planned_at=planned_at,
        duration_minutes=payload.duration_minutes,
        exercises=_normalize_exercise_payload(payload.exercises),
        note=payload.note.strip() if payload.note else None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return build_fitness_session_read(row)


@router.patch("/sessions/{session_id}", response_model=FitnessSessionRead)
def update_fitness_session(session_id: int, payload: FitnessSessionUpdate, session: SessionDep) -> FitnessSessionRead:
    row = session.get(FitnessSession, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Fitness session not found")

    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates and updates["title"] is not None:
        updates["title"] = str(updates["title"]).strip()
    if "note" in updates and updates["note"] is not None:
        updates["note"] = str(updates["note"]).strip() or None
    if "exercises" in updates:
        updates["exercises"] = _normalize_exercise_payload(updates["exercises"])
    if "planned_at" in updates and updates["planned_at"] is not None:
        updates["planned_at"] = _ensure_utc(updates["planned_at"])
    next_planned_at = updates.get("planned_at", row.planned_at)
    next_duration_minutes = updates.get("duration_minutes", row.duration_minutes)
    try:
        validate_calendar_slot_free(
            session,
            next_planned_at,
            next_planned_at + timedelta(minutes=next_duration_minutes),
            source=CalendarSource.FITNESS_SESSION,
            source_ref_id=row.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if "status" in updates and updates["status"] != FitnessSessionStatus.COMPLETED:
        updates["completed_at"] = None
        updates.setdefault("actual_duration_minutes", None)
        updates.setdefault("effort_rating", None)
        updates.setdefault("calories_burned", None)

    for key, value in updates.items():
        setattr(row, key, value)

    if row.status == FitnessSessionStatus.COMPLETED and row.completed_at is None:
        row.completed_at = datetime.now(timezone.utc)

    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return build_fitness_session_read(row)


@router.post("/sessions/{session_id}/complete", response_model=FitnessSessionRead)
def complete_fitness_session(
    session_id: int,
    session: SessionDep,
    payload: FitnessSessionComplete | None = None,
) -> FitnessSessionRead:
    row = session.get(FitnessSession, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Fitness session not found")

    row.status = FitnessSessionStatus.COMPLETED
    row.completed_at = datetime.now(timezone.utc)
    row.actual_duration_minutes = (
        payload.actual_duration_minutes if payload and payload.actual_duration_minutes is not None else row.duration_minutes
    )
    if payload and payload.effort_rating is not None:
        row.effort_rating = payload.effort_rating
    if payload and payload.calories_burned is not None:
        row.calories_burned = payload.calories_burned
    if payload and payload.note is not None:
        row.note = payload.note.strip() or row.note

    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return build_fitness_session_read(row)


@router.delete("/sessions/{session_id}")
def delete_fitness_session(session_id: int, session: SessionDep) -> dict:
    row = session.get(FitnessSession, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Fitness session not found")
    session.delete(row)
    session.commit()
    return {"ok": True, "deleted_id": session_id}


@router.get("/measurements", response_model=list[FitnessMeasurementRead])
def list_fitness_measurements(
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=300),
) -> list[FitnessMeasurementRead]:
    rows = session.exec(select(FitnessMeasurement).order_by(FitnessMeasurement.recorded_at.desc()).limit(limit)).all()
    return [build_fitness_measurement_read(row) for row in rows]


@router.post("/measurements", response_model=FitnessMeasurementRead)
def create_fitness_measurement(payload: FitnessMeasurementCreate, session: SessionDep) -> FitnessMeasurementRead:
    row = FitnessMeasurement(
        recorded_at=_ensure_utc(payload.recorded_at),
        body_weight_kg=payload.body_weight_kg,
        body_fat_pct=payload.body_fat_pct,
        resting_hr=payload.resting_hr,
        sleep_hours=payload.sleep_hours,
        steps=payload.steps,
        note=payload.note.strip() if payload.note else None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return build_fitness_measurement_read(row)


@router.patch("/measurements/{measurement_id}", response_model=FitnessMeasurementRead)
def update_fitness_measurement(
    measurement_id: int,
    payload: FitnessMeasurementUpdate,
    session: SessionDep,
) -> FitnessMeasurementRead:
    row = session.get(FitnessMeasurement, measurement_id)
    if not row:
        raise HTTPException(status_code=404, detail="Fitness measurement not found")

    updates = payload.model_dump(exclude_unset=True)
    if "note" in updates and updates["note"] is not None:
        updates["note"] = str(updates["note"]).strip() or None
    if "recorded_at" in updates and updates["recorded_at"] is not None:
        updates["recorded_at"] = _ensure_utc(updates["recorded_at"])

    for key, value in updates.items():
        setattr(row, key, value)

    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return build_fitness_measurement_read(row)


@router.delete("/measurements/{measurement_id}")
def delete_fitness_measurement(measurement_id: int, session: SessionDep) -> dict:
    row = session.get(FitnessMeasurement, measurement_id)
    if not row:
        raise HTTPException(status_code=404, detail="Fitness measurement not found")
    session.delete(row)
    session.commit()
    return {"ok": True, "deleted_id": measurement_id}
