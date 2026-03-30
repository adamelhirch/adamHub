from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import Habit, HabitFrequency, HabitLog
from app.schemas import HabitCreate, HabitLogCreate, HabitLogRead, HabitRead, HabitUpdate
from app.schemas.dto import _normalize_schedule_times, _normalize_schedule_weekdays
from app.services.calendar_hub import validate_habit_schedule_free
from app.services.life import update_habit_streak

router = APIRouter(prefix="/habits", tags=["habits"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=HabitRead)
def create_habit(payload: HabitCreate, session: SessionDep) -> HabitRead:
    habit = Habit(**payload.model_dump())
    try:
        validate_habit_schedule_free(session, habit)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return HabitRead.model_validate(habit, from_attributes=True)


@router.get("", response_model=list[HabitRead])
def list_habits(session: SessionDep, active_only: bool = True) -> list[HabitRead]:
    statement = select(Habit).order_by(Habit.created_at.desc())
    if active_only:
        statement = statement.where(Habit.active.is_(True))

    habits = session.exec(statement).all()
    return [HabitRead.model_validate(habit, from_attributes=True) for habit in habits]


@router.patch("/{habit_id}", response_model=HabitRead)
def update_habit(habit_id: int, payload: HabitUpdate, session: SessionDep) -> HabitRead:
    habit = session.get(Habit, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    updates = payload.model_dump(exclude_unset=True)
    if "schedule_time" in updates or "schedule_times" in updates:
        schedule_time, schedule_times = _normalize_schedule_times(
            updates.get("schedule_time", habit.schedule_time),
            updates.get("schedule_times", habit.schedule_times),
        )
        updates["schedule_time"] = schedule_time
        updates["schedule_times"] = schedule_times
    if "schedule_weekday" in updates or "schedule_weekdays" in updates:
        schedule_weekday, schedule_weekdays = _normalize_schedule_weekdays(
            updates.get("schedule_weekday", habit.schedule_weekday),
            updates.get("schedule_weekdays", habit.schedule_weekdays),
        )
        updates["schedule_weekday"] = schedule_weekday
        updates["schedule_weekdays"] = schedule_weekdays

    next_frequency = updates.get("frequency", habit.frequency)
    if "schedule_time" in updates and updates["schedule_time"] is None:
        updates["schedule_times"] = []
        updates["schedule_weekday"] = None
        updates["schedule_weekdays"] = []
    if next_frequency == HabitFrequency.DAILY and "schedule_weekday" not in updates:
        if updates.get("frequency") == HabitFrequency.DAILY:
            updates["schedule_weekday"] = None
            updates["schedule_weekdays"] = []
    for key, value in updates.items():
        setattr(habit, key, value)

    if habit.schedule_time is None:
        habit.schedule_times = []
        habit.schedule_weekday = None
        habit.schedule_weekdays = []
    if habit.frequency == HabitFrequency.DAILY:
        habit.schedule_weekday = None
        habit.schedule_weekdays = []

    try:
        validate_habit_schedule_free(session, habit, ignore_habit_id=habit.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    habit.updated_at = datetime.now(timezone.utc)
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return HabitRead.model_validate(habit, from_attributes=True)


@router.post("/{habit_id}/logs", response_model=HabitLogRead)
def log_habit(habit_id: int, payload: HabitLogCreate, session: SessionDep) -> HabitLogRead:
    habit = session.get(Habit, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    log = HabitLog(habit_id=habit_id, **payload.model_dump())
    session.add(log)
    session.commit()
    session.refresh(log)

    update_habit_streak(session, habit_id)

    habit.updated_at = datetime.now(timezone.utc)
    session.add(habit)
    session.commit()

    return HabitLogRead.model_validate(log, from_attributes=True)


@router.get("/{habit_id}/logs", response_model=list[HabitLogRead])
def list_habit_logs(
    habit_id: int,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[HabitLogRead]:
    habit = session.get(Habit, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")

    logs = session.exec(
        select(HabitLog)
        .where(HabitLog.habit_id == habit_id)
        .order_by(HabitLog.logged_at.desc())
        .limit(limit)
    ).all()
    return [HabitLogRead.model_validate(log, from_attributes=True) for log in logs]
