from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import CalendarCategory, CalendarItem, CalendarSource
from app.schemas import (
    CalendarItemCreate,
    CalendarItemRead,
    CalendarItemUpdate,
    CalendarReminderRead,
    CalendarSyncResult,
)
from app.services.calendar_hub import (
    build_calendar_item_read,
    build_ics,
    list_due_reminders,
    sync_generated_calendar_items,
)

router = APIRouter(prefix="/calendar", tags=["calendar"], dependencies=[Depends(require_api_key)])


def _sync_generated(session: SessionDep) -> None:
    sync_generated_calendar_items(session)


@router.post("/items", response_model=CalendarItemRead)
def create_calendar_item(payload: CalendarItemCreate, session: SessionDep) -> CalendarItemRead:
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")

    item = CalendarItem(
        **payload.model_dump(),
        source=CalendarSource.MANUAL,
        generated=False,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return build_calendar_item_read(item)


@router.get("/items", response_model=list[CalendarItemRead])
def list_calendar_items(
    session: SessionDep,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    category: CalendarCategory | None = None,
    source: CalendarSource | None = None,
    include_completed: bool = True,
    generated_only: bool | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[CalendarItemRead]:
    _sync_generated(session)
    statement = select(CalendarItem).order_by(CalendarItem.start_at.asc()).limit(limit)
    if from_at is not None:
        statement = statement.where(CalendarItem.start_at >= from_at)
    if to_at is not None:
        statement = statement.where(CalendarItem.start_at <= to_at)
    if category is not None:
        statement = statement.where(CalendarItem.category == category)
    if source is not None:
        statement = statement.where(CalendarItem.source == source)
    if not include_completed:
        statement = statement.where(CalendarItem.completed.is_(False))
    if generated_only is not None:
        statement = statement.where(CalendarItem.generated == generated_only)

    rows = session.exec(statement).all()
    return [build_calendar_item_read(item) for item in rows]


@router.get("/agenda", response_model=list[CalendarItemRead])
def day_agenda(
    session: SessionDep,
    day: date | None = None,
    include_completed: bool = False,
) -> list[CalendarItemRead]:
    _sync_generated(session)
    if day is None:
        day = datetime.now(UTC).date()

    start = datetime.combine(day, datetime.min.time()).replace(tzinfo=UTC)
    end = start + timedelta(days=1)
    statement = select(CalendarItem).where(CalendarItem.start_at >= start, CalendarItem.start_at < end).order_by(CalendarItem.start_at.asc())
    if not include_completed:
        statement = statement.where(CalendarItem.completed.is_(False))

    rows = session.exec(statement).all()
    return [build_calendar_item_read(item) for item in rows]


@router.get("/items/{item_id}", response_model=CalendarItemRead)
def get_calendar_item(item_id: int, session: SessionDep) -> CalendarItemRead:
    _sync_generated(session)
    item = session.get(CalendarItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar item not found")
    return build_calendar_item_read(item)


@router.patch("/items/{item_id}", response_model=CalendarItemRead)
def update_calendar_item(item_id: int, payload: CalendarItemUpdate, session: SessionDep) -> CalendarItemRead:
    item = session.get(CalendarItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar item not found")
    if item.generated:
        raise HTTPException(status_code=409, detail="Generated calendar items must be updated from their source module")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)

    if item.end_at <= item.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")

    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)
    return build_calendar_item_read(item)


@router.delete("/items/{item_id}")
def delete_calendar_item(item_id: int, session: SessionDep) -> dict:
    item = session.get(CalendarItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar item not found")
    if item.generated:
        raise HTTPException(status_code=409, detail="Generated calendar items must be deleted from their source module")
    session.delete(item)
    session.commit()
    return {"ok": True, "deleted_id": item_id}


@router.post("/sync", response_model=CalendarSyncResult)
def sync_calendar(session: SessionDep) -> CalendarSyncResult:
    synced, removed, by_source = sync_generated_calendar_items(session)
    return CalendarSyncResult(synced=synced, removed=removed, generated_by_source=by_source, synced_at=datetime.now(UTC))


@router.get("/reminders/due", response_model=list[CalendarReminderRead])
def due_reminders(
    session: SessionDep,
    within_minutes: int = Query(default=30, ge=1, le=1440),
) -> list[CalendarReminderRead]:
    _sync_generated(session)
    return list_due_reminders(session, within_minutes=within_minutes)


@router.post("/reminders/{item_id}/ack")
def ack_reminder(item_id: int, session: SessionDep) -> dict:
    item = session.get(CalendarItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Calendar item not found")
    item.last_notified_at = datetime.now(UTC)
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    return {"ok": True, "item_id": item_id, "ack_at": item.last_notified_at.isoformat()}


@router.get("/export.ics", response_class=PlainTextResponse)
def export_calendar_ics(
    session: SessionDep,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    include_completed: bool = True,
    limit: int = Query(default=3000, ge=1, le=10000),
) -> PlainTextResponse:
    _sync_generated(session)
    statement = select(CalendarItem).order_by(CalendarItem.start_at.asc()).limit(limit)
    if from_at is not None:
        statement = statement.where(CalendarItem.start_at >= from_at)
    if to_at is not None:
        statement = statement.where(CalendarItem.start_at <= to_at)
    if not include_completed:
        statement = statement.where(CalendarItem.completed.is_(False))

    items = session.exec(statement).all()
    ics_content = build_ics(items)
    headers = {"Content-Disposition": 'attachment; filename="adamhub-calendar.ics"'}
    return PlainTextResponse(ics_content, headers=headers, media_type="text/calendar")
