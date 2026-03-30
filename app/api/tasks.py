from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import CalendarSource, Task, TaskScheduleMode, TaskStatus
from app.schemas import TaskCreate, TaskRead, TaskUpdate
from app.services.calendar_hub import validate_task_schedule_free

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=TaskRead)
def create_task(payload: TaskCreate, session: SessionDep) -> TaskRead:
    task = Task(**payload.model_dump())
    try:
        validate_task_schedule_free(session, task)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session.add(task)
    session.commit()
    session.refresh(task)
    return TaskRead.model_validate(task, from_attributes=True)


@router.get("", response_model=list[TaskRead])
def list_tasks(
    session: SessionDep,
    status: TaskStatus | None = None,
    only_open: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[TaskRead]:
    statement = select(Task).order_by(Task.created_at.desc()).limit(limit)
    if status:
        statement = statement.where(Task.status == status)
    if only_open:
        statement = statement.where(Task.status != TaskStatus.DONE)

    tasks = session.exec(statement).all()
    return [TaskRead.model_validate(task, from_attributes=True) for task in tasks]


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: int, payload: TaskUpdate, session: SessionDep) -> TaskRead:
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = payload.model_dump(exclude_unset=True)
    if "due_at" in updates and "schedule_mode" not in updates:
        updates["schedule_mode"] = (
            TaskScheduleMode.ONCE if updates["due_at"] is not None else TaskScheduleMode.NONE
        )

    if "schedule_mode" in updates:
        mode = updates["schedule_mode"]
        if mode == TaskScheduleMode.NONE:
            updates["due_at"] = None
            updates["schedule_time"] = None
            updates["schedule_weekday"] = None
        elif mode == TaskScheduleMode.ONCE:
            updates["schedule_time"] = None
            updates["schedule_weekday"] = None
        elif mode == TaskScheduleMode.DAILY:
            updates["due_at"] = None
            updates["schedule_weekday"] = None
        elif mode == TaskScheduleMode.WEEKLY:
            updates["due_at"] = None

    for key, value in updates.items():
        setattr(task, key, value)

    if task.schedule_mode == TaskScheduleMode.NONE and task.due_at is not None:
        task.schedule_mode = TaskScheduleMode.ONCE

    if task.schedule_mode == TaskScheduleMode.ONCE and task.due_at is None:
        task.schedule_mode = TaskScheduleMode.NONE

    try:
        validate_task_schedule_free(session, task, ignore_task_id=task.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    task.updated_at = datetime.now(timezone.utc)
    session.add(task)
    session.commit()
    session.refresh(task)
    return TaskRead.model_validate(task, from_attributes=True)


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(task_id: int, session: SessionDep) -> TaskRead:
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = TaskStatus.DONE
    task.updated_at = datetime.now(timezone.utc)
    session.add(task)
    session.commit()
    session.refresh(task)
    return TaskRead.model_validate(task, from_attributes=True)


@router.delete("/{task_id}")
def delete_task(task_id: int, session: SessionDep) -> dict:
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    session.delete(task)
    session.commit()
    return {"ok": True}
