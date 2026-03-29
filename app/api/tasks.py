from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import CalendarSource, Task, TaskStatus
from app.schemas import TaskCreate, TaskRead, TaskUpdate
from app.services.calendar_hub import validate_calendar_slot_free

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=TaskRead)
def create_task(payload: TaskCreate, session: SessionDep) -> TaskRead:
    task = Task(**payload.model_dump())
    if task.due_at is not None:
        try:
            validate_calendar_slot_free(session, task.due_at, task.due_at + timedelta(minutes=30), source=CalendarSource.TASK)
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
    next_due_at = updates.get("due_at", task.due_at)
    if next_due_at is not None:
        try:
            validate_calendar_slot_free(
                session,
                next_due_at,
                next_due_at + timedelta(minutes=30),
                source=CalendarSource.TASK,
                source_ref_id=task.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    for key, value in updates.items():
        setattr(task, key, value)

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
