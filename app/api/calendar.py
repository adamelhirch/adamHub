from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlmodel import select

from app.api._crud import get_owned_or_404
from app.api.deps import CurrentOrOwnerUser, SessionDep
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
    build_virtual_calendar_item_read,
    build_ics,
    list_due_reminders,
    project_virtual_calendar_items,
    sync_generated_calendar_items,
    validate_calendar_slot_free,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _sort_dt(value: datetime) -> datetime:
    """UTC-normalize for sorting: DB rows are naive-but-UTC, virtual rows are aware."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _sync_generated(session: SessionDep, user: CurrentOrOwnerUser) -> None:
    sync_generated_calendar_items(session, user_id=user.id)


@router.post("/items", response_model=CalendarItemRead)
def create_calendar_item(
    payload: CalendarItemCreate, session: SessionDep, user: CurrentOrOwnerUser
) -> CalendarItemRead:
    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")
    try:
        validate_calendar_slot_free(session, payload.start_at, payload.end_at, user_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    item = CalendarItem(
        **payload.model_dump(),
        source=CalendarSource.MANUAL,
        generated=False,
        user_id=user.id,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return build_calendar_item_read(item)


@router.get("/items", response_model=list[CalendarItemRead])
def list_calendar_items(
    session: SessionDep,
    user: CurrentOrOwnerUser,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    category: CalendarCategory | None = None,
    source: CalendarSource | None = None,
    include_completed: bool = True,
    generated_only: bool | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[CalendarItemRead]:
    _sync_generated(session, user)
    statement = (
        select(CalendarItem)
        .where(CalendarItem.user_id == user.id)
        .order_by(CalendarItem.start_at.asc())
        .limit(limit)
    )
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
    payload = [build_calendar_item_read(item) for item in rows]

    virtual_rows = project_virtual_calendar_items(
        session,
        from_at=from_at,
        to_at=to_at,
        source=source,
        user_id=user.id,
    )
    for row in virtual_rows:
        if category is not None and row["category"] != category:
            continue
        if not include_completed and row["completed"]:
            continue
        payload.append(build_virtual_calendar_item_read(row))

    payload.sort(key=lambda item: _sort_dt(item.start_at))
    return payload[:limit]


@router.get("/agenda", response_model=list[CalendarItemRead])
def day_agenda(
    session: SessionDep,
    user: CurrentOrOwnerUser,
    day: date | None = None,
    include_completed: bool = False,
) -> list[CalendarItemRead]:
    if day is None:
        day = datetime.now(UTC).date()

    start = datetime.combine(day, datetime.min.time()).replace(tzinfo=UTC)
    end = start + timedelta(days=1)
    return list_calendar_items(
        session,
        user=user,
        from_at=start,
        to_at=end,
        include_completed=include_completed,
        limit=500,
    )


@router.get("/items/{item_id}", response_model=CalendarItemRead)
def get_calendar_item(item_id: int, session: SessionDep, user: CurrentOrOwnerUser) -> CalendarItemRead:
    _sync_generated(session, user)
    item = get_owned_or_404(session, CalendarItem, item_id, user_id=user.id, detail="Calendar item not found")
    return build_calendar_item_read(item)


@router.patch("/items/{item_id}", response_model=CalendarItemRead)
def update_calendar_item(
    item_id: int, payload: CalendarItemUpdate, session: SessionDep, user: CurrentOrOwnerUser
) -> CalendarItemRead:
    item = get_owned_or_404(session, CalendarItem, item_id, user_id=user.id, detail="Calendar item not found")
    if item.generated:
        raise HTTPException(status_code=409, detail="Generated calendar items must be updated from their source module")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(item, key, value)

    if item.end_at <= item.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")
    try:
        validate_calendar_slot_free(
            session,
            item.start_at,
            item.end_at,
            ignore_calendar_item_id=item.id,
            user_id=user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)
    return build_calendar_item_read(item)


@router.delete("/items/{item_id}")
def delete_calendar_item(item_id: int, session: SessionDep, user: CurrentOrOwnerUser) -> dict:
    item = get_owned_or_404(session, CalendarItem, item_id, user_id=user.id, detail="Calendar item not found")
    if item.generated:
        raise HTTPException(status_code=409, detail="Generated calendar items must be deleted from their source module")
    session.delete(item)
    session.commit()
    return {"ok": True, "deleted_id": item_id}


@router.post("/sync", response_model=CalendarSyncResult)
def sync_calendar(session: SessionDep, user: CurrentOrOwnerUser) -> CalendarSyncResult:
    synced, removed, by_source = sync_generated_calendar_items(session, user_id=user.id)
    return CalendarSyncResult(synced=synced, removed=removed, generated_by_source=by_source, synced_at=datetime.now(UTC))


@router.get("/reminders/due", response_model=list[CalendarReminderRead])
def due_reminders(
    session: SessionDep,
    user: CurrentOrOwnerUser,
    within_minutes: int = Query(default=30, ge=1, le=1440),
) -> list[CalendarReminderRead]:
    _sync_generated(session, user)
    return list_due_reminders(session, within_minutes=within_minutes, user_id=user.id)


@router.post("/reminders/{item_id}/ack")
def ack_reminder(item_id: int, session: SessionDep, user: CurrentOrOwnerUser) -> dict:
    item = get_owned_or_404(session, CalendarItem, item_id, user_id=user.id, detail="Calendar item not found")
    item.last_notified_at = datetime.now(UTC)
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    return {"ok": True, "item_id": item_id, "ack_at": item.last_notified_at.isoformat()}


@router.get("/export.ics", response_class=PlainTextResponse)
def export_calendar_ics(
    session: SessionDep,
    user: CurrentOrOwnerUser,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    include_completed: bool = True,
    limit: int = Query(default=3000, ge=1, le=10000),
) -> PlainTextResponse:
    _sync_generated(session, user)
    statement = (
        select(CalendarItem)
        .where(CalendarItem.user_id == user.id)
        .order_by(CalendarItem.start_at.asc())
        .limit(limit)
    )
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