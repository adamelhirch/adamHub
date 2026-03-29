from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import CalendarSource, Subscription
from app.schemas import (
    SubscriptionCreate,
    SubscriptionProjection,
    SubscriptionRead,
    SubscriptionUpdate,
)
from app.services.life import build_subscription_projection
from app.services.calendar_hub import validate_calendar_slot_free

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"], dependencies=[Depends(require_api_key)])


def _subscription_slot_start(day: date) -> datetime:
    return datetime.combine(day, time(hour=9, minute=0)).replace(tzinfo=timezone.utc)


@router.post("", response_model=SubscriptionRead)
def create_subscription(payload: SubscriptionCreate, session: SessionDep) -> SubscriptionRead:
    slot_start = _subscription_slot_start(payload.next_due_date)
    try:
        validate_calendar_slot_free(
            session,
            slot_start,
            slot_start + timedelta(minutes=30),
            source=CalendarSource.SUBSCRIPTION,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    sub = Subscription(**payload.model_dump())
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return SubscriptionRead.model_validate(sub, from_attributes=True)


@router.get("", response_model=list[SubscriptionRead])
def list_subscriptions(
    session: SessionDep,
    active_only: bool = True,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[SubscriptionRead]:
    statement = select(Subscription).order_by(Subscription.next_due_date.asc()).limit(limit)
    if active_only:
        statement = statement.where(Subscription.active.is_(True))

    subs = session.exec(statement).all()
    return [SubscriptionRead.model_validate(sub, from_attributes=True) for sub in subs]


@router.get("/upcoming", response_model=list[SubscriptionRead])
def list_upcoming_subscriptions(
    session: SessionDep,
    days: int = Query(default=30, ge=1, le=365),
) -> list[SubscriptionRead]:
    today = date.today()
    until = today + timedelta(days=days)

    subs = session.exec(
        select(Subscription)
        .where(Subscription.active.is_(True), Subscription.next_due_date >= today, Subscription.next_due_date <= until)
        .order_by(Subscription.next_due_date.asc())
    ).all()
    return [SubscriptionRead.model_validate(sub, from_attributes=True) for sub in subs]


@router.get("/projection", response_model=SubscriptionProjection)
def subscription_projection(session: SessionDep, currency: str = "EUR") -> SubscriptionProjection:
    return build_subscription_projection(session, currency=currency)


@router.get("/{subscription_id}", response_model=SubscriptionRead)
def get_subscription(subscription_id: int, session: SessionDep) -> SubscriptionRead:
    sub = session.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return SubscriptionRead.model_validate(sub, from_attributes=True)


@router.patch("/{subscription_id}", response_model=SubscriptionRead)
def update_subscription(subscription_id: int, payload: SubscriptionUpdate, session: SessionDep) -> SubscriptionRead:
    sub = session.get(Subscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    updates = payload.model_dump(exclude_unset=True)
    next_due_date = updates.get("next_due_date", sub.next_due_date)
    slot_start = _subscription_slot_start(next_due_date)
    try:
        validate_calendar_slot_free(
            session,
            slot_start,
            slot_start + timedelta(minutes=30),
            source=CalendarSource.SUBSCRIPTION,
            source_ref_id=sub.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    for key, value in updates.items():
        setattr(sub, key, value)

    sub.updated_at = datetime.now(timezone.utc)
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return SubscriptionRead.model_validate(sub, from_attributes=True)
