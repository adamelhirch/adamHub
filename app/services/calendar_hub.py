from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlmodel import Session, select

from app.models import (
    CalendarCategory,
    CalendarEvent,
    CalendarItem,
    CalendarSource,
    FitnessSession,
    FitnessSessionStatus,
    MealPlan,
    MealPlanCookConfirmation,
    Recipe,
    Subscription,
    Task,
    TaskStatus,
)
from app.schemas import CalendarItemRead, CalendarReminderRead

def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _combine_utc(day: date, value: time) -> datetime:
    return datetime.combine(day, value).replace(tzinfo=UTC)


def build_calendar_item_read(item: CalendarItem) -> CalendarItemRead:
    return CalendarItemRead.model_validate(item, from_attributes=True)


def _intervals_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def _as_utc(value: datetime) -> datetime:
    return _utc(value)


def validate_calendar_slot_free(
    session: Session,
    start_at: datetime,
    end_at: datetime,
    *,
    source: CalendarSource | None = None,
    source_ref_id: int | None = None,
    ignore_calendar_item_id: int | None = None,
) -> None:
    start = _as_utc(start_at)
    end = _as_utc(end_at)
    if end <= start:
        raise ValueError("end_at must be after start_at")

    manual_items = session.exec(select(CalendarItem).where(CalendarItem.generated.is_(False))).all()
    for item in manual_items:
        if ignore_calendar_item_id is not None and item.id == ignore_calendar_item_id:
            continue
        item_start = _as_utc(item.start_at)
        item_end = _as_utc(item.end_at)
        if _intervals_overlap(start, end, item_start, item_end):
            raise ValueError(f"Calendar slot overlaps with existing manual item: {item.title}")

    for row in project_generated_calendar_items(session):
        if source is not None and source_ref_id is not None and row["source"] == source and row["source_ref_id"] == source_ref_id:
            continue
        item_start = _as_utc(row["start_at"])
        item_end = _as_utc(row["end_at"])
        if _intervals_overlap(start, end, item_start, item_end):
            raise ValueError(f"Calendar slot overlaps with generated item: {row['title']}")


def project_generated_calendar_items(session: Session) -> list[dict]:
    projected: list[dict] = []

    tasks = session.exec(select(Task).where(Task.due_at.is_not(None))).all()
    for task in tasks:
        due = _utc(task.due_at)
        projected.append(
            {
                "source": CalendarSource.TASK,
                "source_ref_id": task.id,
                "title": task.title,
                "description": task.description,
                "start_at": due,
                "end_at": due + timedelta(minutes=30),
                "all_day": False,
                "category": CalendarCategory.TASK,
                "completed": task.status == TaskStatus.DONE,
                "notification_enabled": task.status != TaskStatus.DONE,
                "reminder_offsets_min": [120, 30],
                "extra_data": {"task_status": task.status.value, "priority": task.priority.value},
            }
        )

    events = session.exec(select(CalendarEvent)).all()
    for event in events:
        projected.append(
            {
                "source": CalendarSource.EVENT,
                "source_ref_id": event.id,
                "title": event.title,
                "description": event.description,
                "start_at": _utc(event.start_at),
                "end_at": _utc(event.end_at),
                "all_day": event.all_day,
                "category": CalendarCategory.EVENT,
                "completed": False,
                "notification_enabled": True,
                "reminder_offsets_min": [120, 30],
                "extra_data": {"event_type": event.type.value, "location": event.location, "tags": event.tags},
            }
        )

    subs = session.exec(select(Subscription).where(Subscription.active.is_(True))).all()
    for sub in subs:
        due_start = _combine_utc(sub.next_due_date, time(hour=9, minute=0))
        projected.append(
            {
                "source": CalendarSource.SUBSCRIPTION,
                "source_ref_id": sub.id,
                "title": f"Subscription: {sub.name}",
                "description": f"{sub.amount} {sub.currency} ({sub.interval.value})",
                "start_at": due_start,
                "end_at": due_start + timedelta(minutes=30),
                "all_day": True,
                "category": CalendarCategory.SUBSCRIPTION,
                "completed": False,
                "notification_enabled": True,
                "reminder_offsets_min": [1440, 120],
                "extra_data": {
                    "interval": sub.interval.value,
                    "amount": sub.amount,
                    "currency": sub.currency,
                    "autopay": sub.autopay,
                },
            }
        )

    meal_plans = session.exec(select(MealPlan)).all()
    cooked_by_plan = {
        row.meal_plan_id: row for row in session.exec(select(MealPlanCookConfirmation)).all()
    }
    recipes_by_id = {recipe.id: recipe for recipe in session.exec(select(Recipe)).all()}
    for plan in meal_plans:
        if plan.planned_at.tzinfo is None:
            start_at = plan.planned_at.replace(tzinfo=UTC)
        else:
            start_at = plan.planned_at.astimezone(UTC)
        slot_label = plan.slot.value if plan.slot else start_at.strftime("%H:%M")
        end_at = start_at + timedelta(minutes=75)
        recipe = recipes_by_id.get(plan.recipe_id)
        recipe_name = recipe.name if recipe else f"Recipe #{plan.recipe_id}"
        confirmation = cooked_by_plan.get(plan.id)
        cooked_at = confirmation.confirmed_at if confirmation else None
        completed = confirmation is not None
        projected.append(
            {
                "source": CalendarSource.MEAL_PLAN,
                "source_ref_id": plan.id,
                "title": f"Meal ({slot_label}): {recipe_name}",
                "description": plan.note,
                "start_at": start_at,
                "end_at": end_at,
                "all_day": False,
                "category": CalendarCategory.MEAL,
                "completed": completed,
                "notification_enabled": not completed,
                "reminder_offsets_min": [180, 60],
                "extra_data": {
                    "slot": plan.slot.value if plan.slot else None,
                    "recipe_id": plan.recipe_id,
                    "servings_override": plan.servings_override,
                    "cooked_at": cooked_at.isoformat() if cooked_at else None,
                },
            }
        )

    fitness_sessions = session.exec(select(FitnessSession)).all()
    for workout in fitness_sessions:
        if workout.status == FitnessSessionStatus.SKIPPED:
            continue
        start_at = workout.planned_at.astimezone(UTC) if workout.planned_at.tzinfo else workout.planned_at.replace(tzinfo=UTC)
        end_at = start_at + timedelta(minutes=workout.actual_duration_minutes or workout.duration_minutes or 45)
        projected.append(
            {
                "source": CalendarSource.FITNESS_SESSION,
                "source_ref_id": workout.id,
                "title": f"Fitness: {workout.title}",
                "description": workout.note,
                "start_at": start_at,
                "end_at": end_at,
                "all_day": False,
                "category": CalendarCategory.GENERAL,
                "completed": workout.status == FitnessSessionStatus.COMPLETED,
                "notification_enabled": workout.status != FitnessSessionStatus.COMPLETED,
                "reminder_offsets_min": [120, 30],
                "extra_data": {
                    "session_type": workout.session_type.value,
                    "duration_minutes": workout.duration_minutes,
                    "actual_duration_minutes": workout.actual_duration_minutes,
                    "status": workout.status.value,
                    "exercises": workout.exercises or [],
                    "effort_rating": workout.effort_rating,
                    "calories_burned": workout.calories_burned,
                },
            }
        )

    return projected


def sync_generated_calendar_items(session: Session) -> tuple[int, int, dict[str, int]]:
    projected = project_generated_calendar_items(session)
    existing = session.exec(select(CalendarItem).where(CalendarItem.generated.is_(True))).all()
    indexed = {(item.source.value, item.source_ref_id): item for item in existing if item.source_ref_id is not None}

    touched: set[tuple[str, int]] = set()
    synced = 0
    generated_by_source: dict[str, int] = {}

    for row in projected:
        key = (row["source"].value, row["source_ref_id"])
        touched.add(key)
        item = indexed.get(key)
        if item is None:
            item = CalendarItem(generated=True, source=row["source"], source_ref_id=row["source_ref_id"])
        item.title = row["title"]
        item.description = row["description"]
        item.start_at = row["start_at"]
        item.end_at = row["end_at"]
        item.all_day = row["all_day"]
        item.category = row["category"]
        item.completed = row["completed"]
        item.notification_enabled = row["notification_enabled"]
        item.reminder_offsets_min = row["reminder_offsets_min"]
        item.extra_data = row["extra_data"]
        item.updated_at = datetime.now(UTC)
        session.add(item)
        synced += 1
        generated_by_source[row["source"].value] = generated_by_source.get(row["source"].value, 0) + 1

    removed = 0
    for item in existing:
        key = (item.source.value, item.source_ref_id)
        if item.source_ref_id is not None and key not in touched:
            session.delete(item)
            removed += 1

    session.commit()
    return synced, removed, generated_by_source


def list_due_reminders(session: Session, within_minutes: int = 30) -> list[CalendarReminderRead]:
    now = datetime.now(UTC)
    until = now + timedelta(minutes=max(1, within_minutes))
    rows = session.exec(
        select(CalendarItem).where(
            CalendarItem.notification_enabled.is_(True),
            CalendarItem.completed.is_(False),
            CalendarItem.end_at >= now - timedelta(days=1),
        )
    ).all()

    due: list[CalendarReminderRead] = []
    for item in rows:
        offsets = item.reminder_offsets_min or []
        for offset in offsets:
            try:
                minutes_before = int(offset)
            except (TypeError, ValueError):
                continue
            due_at = _utc(item.start_at) - timedelta(minutes=minutes_before)
            if due_at < now or due_at > until:
                continue
            if item.last_notified_at is not None and _utc(item.last_notified_at) >= due_at:
                continue
            due.append(
                CalendarReminderRead(
                    item=build_calendar_item_read(item),
                    due_at=due_at,
                    minutes_before=minutes_before,
                )
            )

    due.sort(key=lambda x: x.due_at)
    return due


def build_ics(items: list[CalendarItem]) -> str:
    def fmt_dt(dt: datetime) -> str:
        return _utc(dt).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AdamHUB//Unified Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    stamp = datetime.now(UTC)
    for item in items:
        uid = f"adamhub-calendar-item-{item.id}@adamhub.local"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{fmt_dt(stamp)}",
                f"DTSTART:{fmt_dt(item.start_at)}",
                f"DTEND:{fmt_dt(item.end_at)}",
                f"SUMMARY:{item.title}",
                f"DESCRIPTION:{(item.description or '').replace(chr(10), '\\n')}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
