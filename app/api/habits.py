from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import Habit, HabitLog
from app.schemas import HabitCreate, HabitLogCreate, HabitLogRead, HabitRead
from app.services.life import update_habit_streak

router = APIRouter(prefix="/habits", tags=["habits"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=HabitRead)
def create_habit(payload: HabitCreate, session: SessionDep) -> HabitRead:
    habit = Habit(**payload.model_dump())
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
