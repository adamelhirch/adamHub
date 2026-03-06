from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import CalendarEvent, EventType
from app.schemas import EventCreate, EventRead, EventUpdate

router = APIRouter(prefix="/events", tags=["events"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=EventRead)
def create_event(payload: EventCreate, session: SessionDep) -> EventRead:
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")

    event = CalendarEvent(**payload.model_dump())
    session.add(event)
    session.commit()
    session.refresh(event)
    return EventRead.model_validate(event, from_attributes=True)


@router.get("", response_model=list[EventRead])
def list_events(
    session: SessionDep,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    type: EventType | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[EventRead]:
    statement = select(CalendarEvent).order_by(CalendarEvent.start_at.asc()).limit(limit)
    if from_at:
        statement = statement.where(CalendarEvent.start_at >= from_at)
    if to_at:
        statement = statement.where(CalendarEvent.start_at <= to_at)
    if type:
        statement = statement.where(CalendarEvent.type == type)

    events = session.exec(statement).all()
    return [EventRead.model_validate(event, from_attributes=True) for event in events]


@router.get("/upcoming", response_model=list[EventRead])
def list_upcoming_events(
    session: SessionDep,
    days: int = Query(default=7, ge=1, le=365),
    type: EventType | None = None,
) -> list[EventRead]:
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=days)
    statement = (
        select(CalendarEvent)
        .where(CalendarEvent.start_at >= now, CalendarEvent.start_at <= until)
        .order_by(CalendarEvent.start_at.asc())
    )
    if type:
        statement = statement.where(CalendarEvent.type == type)

    events = session.exec(statement).all()
    return [EventRead.model_validate(event, from_attributes=True) for event in events]


@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: int, session: SessionDep) -> EventRead:
    event = session.get(CalendarEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventRead.model_validate(event, from_attributes=True)


@router.patch("/{event_id}", response_model=EventRead)
def update_event(event_id: int, payload: EventUpdate, session: SessionDep) -> EventRead:
    event = session.get(CalendarEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(event, key, value)

    if event.end_at <= event.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")

    event.updated_at = datetime.now(timezone.utc)
    session.add(event)
    session.commit()
    session.refresh(event)
    return EventRead.model_validate(event, from_attributes=True)


@router.delete("/{event_id}")
def delete_event(event_id: int, session: SessionDep) -> dict:
    event = session.get(CalendarEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    session.delete(event)
    session.commit()
    return {"ok": True, "deleted_id": event_id}
