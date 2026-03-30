from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from collections.abc import Sequence
import hashlib

from sqlmodel import Session, select

from app.models import (
    CalendarCategory,
    CalendarEvent,
    CalendarItem,
    CalendarSource,
    FitnessSession,
    FitnessSessionStatus,
    Habit,
    HabitFrequency,
    HabitLog,
    MealPlan,
    MealPlanCookConfirmation,
    Recipe,
    Subscription,
    Task,
    TaskScheduleMode,
    TaskStatus,
)
from app.schemas import CalendarItemRead, CalendarReminderRead

RECURRING_LOOKBACK_DAYS = 14
RECURRING_LOOKAHEAD_DAYS = 120
RECURRING_VALIDATION_DAYS = 90


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _combine_utc(day: date, value: time) -> datetime:
    return datetime.combine(day, value).replace(tzinfo=UTC)


def _parse_schedule_time(value: str | None) -> time | None:
    if not value:
        return None
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


def _iter_days(start_day: date, end_day: date):
    current = start_day
    while current <= end_day:
        yield current
        current += timedelta(days=1)


def _effective_task_schedule_mode(task: Task) -> TaskScheduleMode:
    if task.schedule_mode == TaskScheduleMode.NONE and task.due_at is not None:
        return TaskScheduleMode.ONCE
    return task.schedule_mode


def _task_duration_minutes(task: Task) -> int:
    return max(1, task.estimated_minutes or 30)


def _habit_duration_minutes(habit: Habit) -> int:
    return max(1, habit.duration_minutes or 30)


def _habit_schedule_times(habit: Habit) -> list[time]:
    raw_values = [
        value
        for value in [*(habit.schedule_times or []), habit.schedule_time]
        if value
    ]
    unique_values = sorted(set(raw_values))
    parsed: list[time] = []
    for value in unique_values:
        schedule_time = _parse_schedule_time(value)
        if schedule_time is not None:
            parsed.append(schedule_time)
    return parsed


def _habit_schedule_weekdays(habit: Habit) -> list[int]:
    raw_values = [
        value
        for value in [*(habit.schedule_weekdays or []), habit.schedule_weekday]
        if value is not None
    ]
    return sorted(set(raw_values))


def _task_occurrences(task: Task, range_start: datetime, range_end: datetime) -> list[dict]:
    occurrences: list[dict] = []
    mode = _effective_task_schedule_mode(task)
    duration_minutes = _task_duration_minutes(task)

    if mode == TaskScheduleMode.NONE:
        return occurrences

    if mode == TaskScheduleMode.ONCE:
        if task.due_at is None:
            return occurrences
        start_at = _utc(task.due_at)
        end_at = start_at + timedelta(minutes=duration_minutes)
        if _intervals_overlap(start_at, end_at, range_start, range_end):
            occurrences.append(
                {
                    "occurrence_date": start_at.date().isoformat(),
                    "start_at": start_at,
                    "end_at": end_at,
                }
            )
        return occurrences

    schedule_time = _parse_schedule_time(task.schedule_time)
    if schedule_time is None:
        return occurrences

    start_day = range_start.date()
    end_day = range_end.date()
    for day in _iter_days(start_day, end_day):
        if mode == TaskScheduleMode.WEEKLY and task.schedule_weekday != day.weekday():
            continue
        start_at = _combine_utc(day, schedule_time)
        end_at = start_at + timedelta(minutes=duration_minutes)
        if _intervals_overlap(start_at, end_at, range_start, range_end):
            occurrences.append(
                {
                    "occurrence_date": day.isoformat(),
                    "start_at": start_at,
                    "end_at": end_at,
                }
            )

    return occurrences


def _habit_logs_by_day(session: Session) -> dict[int, dict[str, int]]:
    rows = session.exec(select(HabitLog)).all()
    totals: dict[int, dict[str, int]] = {}
    for row in rows:
        bucket = totals.setdefault(row.habit_id, {})
        day_key = _utc(row.logged_at).date().isoformat()
        bucket[day_key] = bucket.get(day_key, 0) + int(row.value or 0)
    return totals


def _habit_occurrences(
    habit: Habit,
    range_start: datetime,
    range_end: datetime,
    *,
    habit_logs_by_day: dict[int, dict[str, int]] | None = None,
) -> list[dict]:
    occurrences: list[dict] = []
    if not habit.active:
        return occurrences

    schedule_times = _habit_schedule_times(habit)
    if not schedule_times:
        return occurrences

    start_day = range_start.date()
    end_day = range_end.date()
    duration_minutes = _habit_duration_minutes(habit)
    per_day_totals = (habit_logs_by_day or {}).get(habit.id or -1, {})
    schedule_weekdays = _habit_schedule_weekdays(habit)

    for day in _iter_days(start_day, end_day):
        if (
            habit.frequency == HabitFrequency.WEEKLY
            and day.weekday() not in schedule_weekdays
        ):
            continue
        completed = per_day_totals.get(day.isoformat(), 0) >= max(1, habit.target_per_period)
        for schedule_time in schedule_times:
            start_at = _combine_utc(day, schedule_time)
            end_at = start_at + timedelta(minutes=duration_minutes)
            if not _intervals_overlap(start_at, end_at, range_start, range_end):
                continue

            occurrences.append(
                {
                    "occurrence_date": day.isoformat(),
                    "occurrence_time": schedule_time.strftime("%H:%M"),
                    "start_at": start_at,
                    "end_at": end_at,
                    "completed": completed,
                }
            )

    return occurrences


def _virtual_calendar_item_id(
    source: CalendarSource,
    source_ref_id: int,
    occurrence_key: str,
) -> int:
    raw = f"{source.value}:{source_ref_id}:{occurrence_key}".encode("utf-8")
    digest = hashlib.sha1(raw).digest()
    return -int.from_bytes(digest[:4], "big", signed=False)


def build_calendar_item_read(item: CalendarItem) -> CalendarItemRead:
    return CalendarItemRead.model_validate(item, from_attributes=True)


def build_virtual_calendar_item_read(row: dict) -> CalendarItemRead:
    return CalendarItemRead(
        id=row["id"],
        title=row["title"],
        description=row.get("description"),
        start_at=row["start_at"],
        end_at=row["end_at"],
        all_day=row.get("all_day", False),
        category=row.get("category", CalendarCategory.GENERAL),
        source=row["source"],
        source_ref_id=row.get("source_ref_id"),
        generated=True,
        completed=row.get("completed", False),
        notification_enabled=row.get("notification_enabled", True),
        reminder_offsets_min=row.get("reminder_offsets_min", [60]),
        extra_data=row.get("extra_data", {}),
        last_notified_at=None,
        created_at=row["start_at"],
        updated_at=row["start_at"],
    )


def _intervals_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and start_b < end_a


def _as_utc(value: datetime) -> datetime:
    return _utc(value)


def _resolve_virtual_window(
    from_at: datetime | None,
    to_at: datetime | None,
) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    start = _utc(from_at) if from_at is not None else now - timedelta(days=RECURRING_LOOKBACK_DAYS)
    end = _utc(to_at) if to_at is not None else now + timedelta(days=RECURRING_LOOKAHEAD_DAYS)
    if end <= start:
        end = start + timedelta(days=1)
    return start, end


def project_persisted_generated_calendar_items(session: Session) -> list[dict]:
    projected: list[dict] = []

    tasks = session.exec(select(Task).where(Task.due_at.is_not(None))).all()
    for task in tasks:
        if _effective_task_schedule_mode(task) != TaskScheduleMode.ONCE:
            continue
        due = _utc(task.due_at)
        projected.append(
            {
                "source": CalendarSource.TASK,
                "source_ref_id": task.id,
                "title": task.title,
                "description": task.description,
                "start_at": due,
                "end_at": due + timedelta(minutes=_task_duration_minutes(task)),
                "all_day": False,
                "category": CalendarCategory.TASK,
                "completed": task.status == TaskStatus.DONE,
                "notification_enabled": task.status != TaskStatus.DONE,
                "reminder_offsets_min": [120, 30],
                "extra_data": {
                    "task_status": task.status.value,
                    "priority": task.priority.value,
                    "schedule_mode": TaskScheduleMode.ONCE.value,
                },
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
                "extra_data": {
                    "event_type": event.type.value,
                    "location": event.location,
                    "tags": event.tags,
                },
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
        start_at = _utc(plan.planned_at)
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
        start_at = _utc(workout.planned_at)
        end_at = start_at + timedelta(
            minutes=workout.actual_duration_minutes or workout.duration_minutes or 45
        )
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


def project_virtual_calendar_items(
    session: Session,
    *,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
    source: CalendarSource | None = None,
) -> list[dict]:
    projected: list[dict] = []
    range_start, range_end = _resolve_virtual_window(from_at, to_at)

    if source in (None, CalendarSource.TASK):
        tasks = session.exec(select(Task)).all()
        for task in tasks:
            mode = _effective_task_schedule_mode(task)
            if mode not in {TaskScheduleMode.DAILY, TaskScheduleMode.WEEKLY}:
                continue

            for occurrence in _task_occurrences(task, range_start, range_end):
                occurrence_date = occurrence["occurrence_date"]
                projected.append(
                    {
                        "id": _virtual_calendar_item_id(CalendarSource.TASK, task.id or 0, occurrence_date),
                        "source": CalendarSource.TASK,
                        "source_ref_id": task.id,
                        "title": task.title,
                        "description": task.description,
                        "start_at": occurrence["start_at"],
                        "end_at": occurrence["end_at"],
                        "all_day": False,
                        "category": CalendarCategory.TASK,
                        "completed": task.status == TaskStatus.DONE,
                        "notification_enabled": task.status != TaskStatus.DONE,
                        "reminder_offsets_min": [120, 30],
                        "extra_data": {
                            "task_status": task.status.value,
                            "priority": task.priority.value,
                            "schedule_mode": mode.value,
                            "schedule_time": task.schedule_time,
                            "schedule_weekday": task.schedule_weekday,
                            "occurrence_date": occurrence_date,
                            "virtual": True,
                        },
                    }
                )

    if source in (None, CalendarSource.HABIT):
        habits = session.exec(select(Habit).where(Habit.active.is_(True))).all()
        logs_by_day = _habit_logs_by_day(session)
        for habit in habits:
            if habit.schedule_time is None:
                continue

            for occurrence in _habit_occurrences(
                habit,
                range_start,
                range_end,
                habit_logs_by_day=logs_by_day,
            ):
                occurrence_date = occurrence["occurrence_date"]
                occurrence_time = occurrence["occurrence_time"]
                projected.append(
                    {
                        "id": _virtual_calendar_item_id(
                            CalendarSource.HABIT,
                            habit.id or 0,
                            f"{occurrence_date}:{occurrence_time}",
                        ),
                        "source": CalendarSource.HABIT,
                        "source_ref_id": habit.id,
                        "title": habit.name,
                        "description": habit.description,
                        "start_at": occurrence["start_at"],
                        "end_at": occurrence["end_at"],
                        "all_day": False,
                        "category": CalendarCategory.TASK,
                        "completed": occurrence["completed"],
                        "notification_enabled": habit.active,
                        "reminder_offsets_min": [60, 15],
                        "extra_data": {
                            "habit_frequency": habit.frequency.value,
                            "target_per_period": habit.target_per_period,
                            "schedule_time": habit.schedule_time,
                            "schedule_times": habit.schedule_times,
                            "schedule_weekday": habit.schedule_weekday,
                            "schedule_weekdays": habit.schedule_weekdays,
                            "duration_minutes": habit.duration_minutes,
                            "occurrence_date": occurrence_date,
                            "occurrence_time": occurrence_time,
                            "virtual": True,
                        },
                    }
                )

    projected.sort(key=lambda row: row["start_at"])
    return projected


def project_generated_calendar_items(
    session: Session,
    *,
    from_at: datetime | None = None,
    to_at: datetime | None = None,
) -> list[dict]:
    projected = project_persisted_generated_calendar_items(session)
    projected.extend(
        project_virtual_calendar_items(session, from_at=from_at, to_at=to_at)
    )
    projected.sort(key=lambda row: row["start_at"])
    return projected


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

    for row in project_generated_calendar_items(
        session,
        from_at=start - timedelta(days=1),
        to_at=end + timedelta(days=1),
    ):
        if (
            source is not None
            and source_ref_id is not None
            and row["source"] == source
            and row["source_ref_id"] == source_ref_id
        ):
            continue
        item_start = _as_utc(row["start_at"])
        item_end = _as_utc(row["end_at"])
        if _intervals_overlap(start, end, item_start, item_end):
            raise ValueError(f"Calendar slot overlaps with generated item: {row['title']}")


def validate_task_schedule_free(
    session: Session,
    task: Task,
    *,
    ignore_task_id: int | None = None,
) -> None:
    mode = _effective_task_schedule_mode(task)
    if mode == TaskScheduleMode.ONCE and task.due_at is not None:
        start_at = _utc(task.due_at)
        range_start = start_at - timedelta(minutes=1)
        range_end = start_at + timedelta(minutes=_task_duration_minutes(task) + 1)
    else:
        range_start = datetime.now(UTC)
        range_end = range_start + timedelta(days=RECURRING_VALIDATION_DAYS)

    for occurrence in _task_occurrences(task, range_start, range_end):
        validate_calendar_slot_free(
            session,
            occurrence["start_at"],
            occurrence["end_at"],
            source=CalendarSource.TASK,
            source_ref_id=ignore_task_id or task.id,
        )


def validate_habit_schedule_free(
    session: Session,
    habit: Habit,
    *,
    ignore_habit_id: int | None = None,
) -> None:
    range_start = datetime.now(UTC)
    range_end = range_start + timedelta(days=RECURRING_VALIDATION_DAYS)
    occurrences = _habit_occurrences(habit, range_start, range_end)
    sorted_occurrences = sorted(occurrences, key=lambda row: row["start_at"])
    for previous, current in zip(sorted_occurrences, sorted_occurrences[1:]):
        if _intervals_overlap(
            previous["start_at"],
            previous["end_at"],
            current["start_at"],
            current["end_at"],
        ):
            raise ValueError("Habit schedule overlaps with itself")

    for occurrence in occurrences:
        validate_calendar_slot_free(
            session,
            occurrence["start_at"],
            occurrence["end_at"],
            source=CalendarSource.HABIT,
            source_ref_id=ignore_habit_id or habit.id,
        )


def sync_generated_calendar_items(session: Session) -> tuple[int, int, dict[str, int]]:
    projected = project_persisted_generated_calendar_items(session)
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


def _calendar_attr(item, name: str):
    if isinstance(item, dict):
        return item.get(name)
    return getattr(item, name)


def _escape_ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def build_ics(items: Sequence, *, calendar_name: str = "AdamHUB") -> str:
    def fmt_dt(dt: datetime) -> str:
        return _utc(dt).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AdamHUB//Unified Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape_ics_text(calendar_name)}",
        f"NAME:{_escape_ics_text(calendar_name)}",
    ]

    stamp = datetime.now(UTC)
    for item in items:
        item_id = _calendar_attr(item, "id")
        start_at = _calendar_attr(item, "start_at")
        end_at = _calendar_attr(item, "end_at")
        title = _calendar_attr(item, "title")
        description = _calendar_attr(item, "description")
        uid = f"adamhub-calendar-item-{item_id}@adamhub.local"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{fmt_dt(stamp)}",
                f"DTSTART:{fmt_dt(start_at)}",
                f"DTEND:{fmt_dt(end_at)}",
                f"SUMMARY:{_escape_ics_text(title)}",
                f"DESCRIPTION:{_escape_ics_text(description or '')}",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
