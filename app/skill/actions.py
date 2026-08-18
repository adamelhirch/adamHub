import asyncio
from datetime import date, datetime, time, timedelta, timezone

from sqlmodel import select

from app.api._crud import apply_updates, create, delete, save
from app.models import (
    Account,
    Budget,
    CalendarCategory,
    CalendarEvent,
    CalendarItem,
    CalendarSource,
    EventType,
    FinanceTransaction,
    FitnessMeasurement,
    FitnessSession,
    FitnessSessionStatus,
    Goal,
    GoalMilestone,
    GoalStatus,
    GroceryItem,
    GroceryPantrySync,
    Habit,
    HabitFrequency,
    HabitLog,
    MealPlan,
    MealPlanCookConfirmation,
    MealSlot,
    Note,
    NoteKind,
    PantryItem,
    Recipe,
    RecipeIngredient,
    SavingsGoal,
    Subscription,
    SubscriptionInterval,
    SupermarketConnection,
    SupermarketSearchCache,
    SupermarketStore,
    Task,
    TaskStatus,
    TransactionKind,
    User,
)
from app.schemas import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    BudgetCreate,
    CalendarItemCreate,
    CalendarItemUpdate,
    EventCreate,
    EventUpdate,
    FinanceTransactionCreate,
    FitnessMeasurementCreate,
    FitnessMeasurementUpdate,
    FitnessSessionComplete,
    FitnessSessionCreate,
    FitnessSessionUpdate,
    GoalCreate,
    GoalMilestoneCreate,
    GoalMilestoneUpdate,
    GoalUpdate,
    GroceryItemCreate,
    GroceryItemUpdate,
    HabitCreate,
    HabitUpdate,
    MealPlanCreate,
    MealPlanUpdate,
    NoteCreate,
    NoteUpdate,
    PantryItemCreate,
    PantryItemUpdate,
    SavingsGoalCreate,
    SavingsGoalRead,
    SavingsGoalUpdate,
    RecipeCreate,
    RecipeUpdate,
    SubscriptionCreate,
    SubscriptionUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.schemas.dto import (
    _normalize_schedule_times,
    _normalize_schedule_weekdays,
)
from app.services.life import (
    build_dashboard_overview,
    build_month_summary,
    build_pantry_overview,
    build_recipe_read,
    build_subscription_projection,
    list_upcoming_events,
    list_upcoming_subscriptions,
    update_habit_streak,
)
from app.services.cook import (
    confirm_meal_plan_cooked,
    confirm_recipe_cooked,
    reset_meal_plan_cook_confirmation,
    unconfirm_meal_plan_cooked,
    unconfirm_recipe_cooked,
)
from app.services.meal_planning import (
    build_meal_plan_read,
    build_meal_plan_reads,
    resolve_recipe_ingredient_fields,
    sync_meal_plan_to_grocery,
    validate_meal_plan_slot_free,
    visible_meal_plans,
)
from app.services.calendar_hub import (
    apply_task_update,
    build_calendar_item_read,
    list_due_reminders,
    sync_generated_calendar_items,
    validate_habit_schedule_free,
    validate_task_schedule_free,
    validate_calendar_slot_free,
)
from app.services.fitness import (
    _ensure_utc,
    build_fitness_measurement_read,
    build_fitness_overview,
    build_fitness_session_read,
    coerce_fitness_exercises,
)
from app.services.grocery_pantry import sync_checked_grocery_item_to_pantry
from app.services.connections import (
    activate_connection as activate_supermarket_connection,
    delete_connection as delete_supermarket_connection,
    list_connections as list_supermarket_connections,
    upsert_connection as upsert_supermarket_connection,
    decrypt_cookies as decrypt_connection_cookies,
)
from app.services.store_catalog import (
    fetch_search_results,
    get_selected_store as get_selected_supermarket_store,
    list_store_definitions,
    load_active_cookies,
    upsert_search_cache,
    upsert_selected_store,
)
from app.services.scrapers.auchan import (
    AuchanAuthError,
    AuchanStoreContext,
    list_auchan_offering_contexts,
    load_auchan_cookies,
    select_auchan_store,
)
from app.services.video_intake import extract_video_source


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    return bool(value)


def _clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _int_id(payload: dict, field: str) -> int:
    """Parse a scalar record id from a skill payload, raising ValueError on any
    malformed input (missing, boolean, non-numeric string, or non-scalar JSON).

    Unlike raw ``int(payload.get(field, 0))`` — which leaks a TypeError on a
    list/dict value — this never raises outside ValueError, so skill_execute
    converts every parsing failure into a clean 400.
    """
    value = payload.get(field)
    if value is None:
        raise ValueError(f"{field} is required")
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field} must be an integer") from exc
    raise ValueError(f"{field} must be an integer")


def _parse_datetime(value, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be ISO datetime") from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise ValueError(f"{field_name} must be datetime")


def _parse_date(value, field_name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be in YYYY-MM-DD format") from exc
    raise ValueError(f"{field_name} must be date")


_SLOT_DEFAULT_TIME: dict[str, time] = {
    "breakfast": time(hour=8, minute=0),
    "lunch": time(hour=12, minute=30),
    "dinner": time(hour=19, minute=30),
}


def _subscription_slot_start(day: date) -> datetime:
    """Mirror of app/api/subscriptions.py — subscriptions own the 9:00 slot."""
    return datetime.combine(day, time(hour=9, minute=0)).replace(tzinfo=timezone.utc)


def _resolve_meal_planned_at(payload: dict, current: datetime | None = None) -> datetime:
    planned_at = _parse_datetime(payload.get("planned_at"), "planned_at")
    if planned_at is not None:
        return planned_at

    planned_for = _parse_date(payload.get("planned_for"), "planned_for")
    if planned_for is not None:
        slot = str(payload.get("slot") or "").strip().lower()
        slot_time = _SLOT_DEFAULT_TIME.get(slot, time(hour=12, minute=0))
        return datetime.combine(planned_for, slot_time).replace(tzinfo=timezone.utc)

    if current is not None:
        return current
    return datetime.now(timezone.utc)


def _build_account_read_payload(account: Account) -> dict:
    return AccountRead.model_validate(account, from_attributes=True).model_dump(mode="json")


def _build_savings_goal_read_payload(goal: SavingsGoal, accounts_by_id: dict[int, Account]) -> dict:
    read = SavingsGoalRead.model_validate(goal, from_attributes=True)
    if goal.account_id and goal.account_id in accounts_by_id:
        read.current_amount = accounts_by_id[goal.account_id].balance
    return read.model_dump(mode="json")


def _get_owned_recipe(session, recipe_id: int, user_id: int) -> Recipe:
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    return recipe


def _get_owned_meal_plan(session, meal_plan_id: int, user_id: int) -> MealPlan:
    plan = session.get(MealPlan, meal_plan_id)
    if not plan or plan.user_id != user_id:
        raise ValueError("meal_plan_id not found")
    return plan


def _get_owned_note(session, note_id: int, user_id: int) -> Note:
    note = session.get(Note, note_id)
    if not note or note.user_id != user_id:
        raise ValueError("note_id not found")
    return note


def _is_owner_user(user: User | None) -> bool:
    """True when the acting user is the configured ADAMHUB_OWNER_EMAIL user."""
    if user is None:
        return False
    from app.core.config import get_settings

    settings = get_settings()
    owner_email = (settings.owner_email or "").strip().lower()
    return bool(owner_email) and (user.email or "").strip().lower() == owner_email


def _connection_is_operable(connection, user: User | None) -> bool:
    """A connection can be listed/activated/deleted by the acting user."""
    if connection is None:
        return True
    if connection.user_id is not None:
        return user is not None and connection.user_id == user.id
    return _is_owner_user(user)


def _handle_task_create(payload, session, *, user, now, user_id):
    data = TaskCreate.model_validate(payload)
    task = Task(**data.model_dump())
    validate_task_schedule_free(session, task)
    task = create(session, task)
    return {"task": task.model_dump(mode="json")}


def _handle_task_list(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=25, minimum=1, maximum=100)
    only_open = _as_bool(payload.get("only_open"), default=False)
    statement = select(Task).order_by(Task.created_at.desc()).limit(limit)

    if payload.get("status"):
        statement = statement.where(Task.status == TaskStatus(payload["status"]))
    if only_open:
        statement = statement.where(Task.status != TaskStatus.DONE)

    tasks = session.exec(statement).all()
    return {"tasks": [task.model_dump(mode="json") for task in tasks]}


def _handle_task_update(payload, session, *, user, now, user_id):
    task_id = _int_id(payload, "task_id")
    task = session.get(Task, task_id)
    if not task:
        raise ValueError("task_id not found")

    patch = TaskUpdate.model_validate({k: v for k, v in payload.items() if k != "task_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No task fields to update")

    apply_task_update(task, updates)

    validate_task_schedule_free(session, task, ignore_task_id=task.id)
    task.updated_at = now

    session.add(task)
    session.commit()
    session.refresh(task)
    return {"task": task.model_dump(mode="json")}


def _handle_task_complete(payload, session, *, user, now, user_id):
    task_id = _int_id(payload, "task_id")
    task = session.get(Task, task_id)
    if not task:
        raise ValueError("task_id not found")
    task.status = TaskStatus.DONE
    task.updated_at = now
    task = save(session, task)
    return {"task": task.model_dump(mode="json")}


def _handle_task_delete(payload, session, *, user, now, user_id):
    task_id = _int_id(payload, "task_id")
    task = session.get(Task, task_id)
    if not task:
        raise ValueError("task_id not found")
    delete(session, task)
    return {"ok": True, "deleted_id": task_id}


def _handle_finance_add_transaction(payload, session, *, user, now, user_id):
    data = FinanceTransactionCreate.model_validate(payload)
    tx = FinanceTransaction(**data.model_dump(), user_id=user_id)
    if tx.occurred_at is None:
        tx.occurred_at = now
    tx = create(session, tx)
    return {"transaction": tx.model_dump(mode="json")}


def _handle_finance_list_transactions(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=300)
    statement = (
        select(FinanceTransaction)
        .where(FinanceTransaction.user_id == user_id)
        .order_by(FinanceTransaction.occurred_at.desc())
        .limit(limit)
    )

    if payload.get("kind"):
        statement = statement.where(FinanceTransaction.kind == TransactionKind(payload["kind"]))

    year = payload.get("year")
    month = payload.get("month")
    if year is not None and month is not None:
        year = int(year)
        month = int(month)
        if month < 1 or month > 12:
            raise ValueError("month must be between 1 and 12")
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(year, month + 1, 1, tzinfo=timezone.utc)
        statement = statement.where(
            FinanceTransaction.occurred_at >= start,
            FinanceTransaction.occurred_at < end,
        )

    txs = session.exec(statement).all()
    return {"transactions": [tx.model_dump(mode="json") for tx in txs]}


def _handle_finance_create_budget(payload, session, *, user, now, user_id):
    data = BudgetCreate.model_validate(payload)
    if len(data.month) != 7 or data.month[4] != "-":
        raise ValueError("month must be in format YYYY-MM")
    budget = create(session, Budget(**data.model_dump(), user_id=user_id))
    return {"budget": budget.model_dump(mode="json")}


def _handle_finance_list_budgets(payload, session, *, user, now, user_id):
    statement = (
        select(Budget)
        .where(Budget.user_id == user_id)
        .order_by(Budget.month.desc(), Budget.category.asc())
    )
    if payload.get("month"):
        statement = statement.where(Budget.month == payload["month"])
    budgets = session.exec(statement).all()
    return {"budgets": [budget.model_dump(mode="json") for budget in budgets]}


def _handle_finance_month_summary(payload, session, *, user, now, user_id):
    year = int(payload.get("year", now.year))
    month = int(payload.get("month", now.month))
    summary = build_month_summary(session, year, month, user_id=user_id)
    return {"summary": summary.model_dump(mode="json")}


def _handle_fitness_overview(payload, session, *, user, now, user_id):
    return {"overview": build_fitness_overview(session).model_dump(mode="json")}


def _handle_fitness_list_sessions(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=300)
    rows = session.exec(
        select(FitnessSession).order_by(FitnessSession.planned_at.desc()).limit(limit)
    ).all()
    return {"sessions": [build_fitness_session_read(row).model_dump(mode="json") for row in rows]}


def _handle_fitness_create_session(payload, session, *, user, now, user_id):
    data = FitnessSessionCreate.model_validate(payload)
    planned_at = _ensure_utc(data.planned_at)
    validate_calendar_slot_free(
        session,
        planned_at,
        planned_at + timedelta(minutes=data.duration_minutes),
        source=CalendarSource.FITNESS_SESSION,
    )
    row = FitnessSession(
        title=data.title.strip(),
        session_type=data.session_type,
        planned_at=planned_at,
        duration_minutes=data.duration_minutes,
        exercises=coerce_fitness_exercises(data.exercises),
        note=data.note.strip() if data.note else None,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"session": build_fitness_session_read(row).model_dump(mode="json")}


def _handle_fitness_update_session(payload, session, *, user, now, user_id):
    session_id = _int_id(payload, "session_id")
    row = session.get(FitnessSession, session_id)
    if not row:
        raise ValueError("session_id not found")

    patch = FitnessSessionUpdate.model_validate(
        {k: v for k, v in payload.items() if k != "session_id"}
    )
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No fitness session fields to update")

    if "title" in updates and updates["title"] is not None:
        updates["title"] = str(updates["title"]).strip()
    if "note" in updates and updates["note"] is not None:
        updates["note"] = str(updates["note"]).strip() or None
    if "exercises" in updates:
        updates["exercises"] = coerce_fitness_exercises(updates["exercises"])
    if "planned_at" in updates and updates["planned_at"] is not None:
        updates["planned_at"] = _ensure_utc(updates["planned_at"])

    next_planned_at = updates.get("planned_at", row.planned_at)
    next_duration_minutes = updates.get("duration_minutes", row.duration_minutes)
    validate_calendar_slot_free(
        session,
        next_planned_at,
        next_planned_at + timedelta(minutes=next_duration_minutes),
        source=CalendarSource.FITNESS_SESSION,
        source_ref_id=row.id,
    )

    if "status" in updates and updates["status"] != FitnessSessionStatus.COMPLETED:
        updates["completed_at"] = None
        updates.setdefault("actual_duration_minutes", None)
        updates.setdefault("effort_rating", None)
        updates.setdefault("calories_burned", None)

    for key, value in updates.items():
        setattr(row, key, value)

    if row.status == FitnessSessionStatus.COMPLETED and row.completed_at is None:
        row.completed_at = now

    row.updated_at = now
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"session": build_fitness_session_read(row).model_dump(mode="json")}


def _handle_fitness_complete_session(payload, session, *, user, now, user_id):
    session_id = _int_id(payload, "session_id")
    row = session.get(FitnessSession, session_id)
    if not row:
        raise ValueError("session_id not found")

    completion = FitnessSessionComplete.model_validate(
        {k: v for k, v in payload.items() if k != "session_id"}
    )
    row.status = FitnessSessionStatus.COMPLETED
    row.completed_at = now
    row.actual_duration_minutes = completion.actual_duration_minutes or row.duration_minutes
    if completion.effort_rating is not None:
        row.effort_rating = completion.effort_rating
    if completion.calories_burned is not None:
        row.calories_burned = completion.calories_burned
    if completion.note is not None:
        row.note = completion.note.strip() or row.note
    row.updated_at = now
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"session": build_fitness_session_read(row).model_dump(mode="json")}


def _handle_fitness_delete_session(payload, session, *, user, now, user_id):
    session_id = _int_id(payload, "session_id")
    row = session.get(FitnessSession, session_id)
    if not row:
        raise ValueError("session_id not found")
    delete(session, row)
    return {"ok": True, "deleted_id": session_id}


def _handle_fitness_list_measurements(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=300)
    rows = session.exec(
        select(FitnessMeasurement)
        .order_by(FitnessMeasurement.recorded_at.desc())
        .limit(limit)
    ).all()
    return {
        "measurements": [
            build_fitness_measurement_read(row).model_dump(mode="json") for row in rows
        ]
    }


def _handle_fitness_add_measurement(payload, session, *, user, now, user_id):
    data = FitnessMeasurementCreate.model_validate(payload)
    row = FitnessMeasurement(
        recorded_at=_ensure_utc(data.recorded_at),
        body_weight_kg=data.body_weight_kg,
        body_fat_pct=data.body_fat_pct,
        resting_hr=data.resting_hr,
        sleep_hours=data.sleep_hours,
        steps=data.steps,
        note=data.note.strip() if data.note else None,
    )
    row = create(session, row)
    return {"measurement": build_fitness_measurement_read(row).model_dump(mode="json")}


def _handle_fitness_update_measurement(payload, session, *, user, now, user_id):
    measurement_id = _int_id(payload, "measurement_id")
    row = session.get(FitnessMeasurement, measurement_id)
    if not row:
        raise ValueError("measurement_id not found")

    patch = FitnessMeasurementUpdate.model_validate(
        {k: v for k, v in payload.items() if k != "measurement_id"}
    )
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No fitness measurement fields to update")

    if "note" in updates and updates["note"] is not None:
        updates["note"] = str(updates["note"]).strip() or None
    if "recorded_at" in updates and updates["recorded_at"] is not None:
        updates["recorded_at"] = _ensure_utc(updates["recorded_at"])

    apply_updates(row, updates, touch=True)
    row = save(session, row)
    return {"measurement": build_fitness_measurement_read(row).model_dump(mode="json")}


def _handle_fitness_delete_measurement(payload, session, *, user, now, user_id):
    measurement_id = _int_id(payload, "measurement_id")
    row = session.get(FitnessMeasurement, measurement_id)
    if not row:
        raise ValueError("measurement_id not found")
    delete(session, row)
    return {"ok": True, "deleted_id": measurement_id}


def _handle_grocery_add_item(payload, session, *, user, now, user_id):
    data = GroceryItemCreate.model_validate(payload)
    item = create(session, GroceryItem(**data.model_dump(), user_id=user_id))
    return {"item": item.model_dump(mode="json")}


def _handle_supermarket_list_stores(payload, session, *, user, now, user_id):
    return {
        "stores": [
            {
                "key": definition.key.value,
                "label": definition.label,
                "supports_search": definition.supports_search,
                "supports_mapping": definition.supports_mapping,
                "supports_cart_automation": definition.supports_cart_automation,
                "scraper_name": definition.scraper_name,
                "notes": definition.notes,
            }
            for definition in list_store_definitions()
        ]
    }


def _handle_supermarket_list_connections(payload, session, *, user, now, user_id):
    store_key = payload.get("store")
    store_enum = SupermarketStore(store_key.lower()) if store_key else None
    rows = list_supermarket_connections(session, store_enum, user_id=user_id)
    if _is_owner_user(user):
        # Legacy (pre-scoping) connections with a NULL user_id belong to the
        # single-user owner and must remain visible to the legacy path.
        rows += list_supermarket_connections(session, store_enum, user_id=None)

    def _read(row):
        try:
            count = len(decrypt_connection_cookies(row))
        except Exception:
            count = 0
        return {
            "id": row.id,
            "store": row.store.value,
            "label": row.label,
            "is_active": row.is_active,
            "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "cookies_count": count,
        }

    return {"connections": [_read(r) for r in rows]}


def _handle_supermarket_import_connection(payload, session, *, user, now, user_id):
    store_enum = SupermarketStore(str(payload.get("store") or "").lower())
    cookies = payload.get("cookies") or []
    credentials = payload.get("credentials")
    if not isinstance(cookies, list):
        raise ValueError("cookies must be a list")
    if not cookies and not isinstance(credentials, dict):
        raise ValueError("cookies or credentials are required")
    label = (payload.get("label") or "").strip() or f"{store_enum.value}-connection"
    connection = upsert_supermarket_connection(
        session,
        store=store_enum,
        label=label,
        cookies=cookies,
        credentials=credentials,
        activate=_as_bool(payload.get("activate"), default=True),
        connection_id=payload.get("connection_id"),
        user_id=user_id,
    )
    return {
        "connection": {
            "id": connection.id,
            "store": connection.store.value,
            "label": connection.label,
            "is_active": connection.is_active,
            "cookies_count": len(cookies),
        }
    }


def _handle_supermarket_activate_connection(payload, session, *, user, now, user_id):
    connection_id = _int_id(payload, "connection_id")
    if not connection_id:
        raise ValueError("connection_id is required")
    existing = session.get(SupermarketConnection, connection_id)
    if not _connection_is_operable(existing, user):
        raise ValueError("Connection not found")
    connection = activate_supermarket_connection(session, connection_id, user_id=user_id)
    if connection is None:
        raise ValueError("Connection not found")
    return {"connection": {"id": connection.id, "store": connection.store.value, "is_active": True}}


def _handle_supermarket_delete_connection(payload, session, *, user, now, user_id):
    connection_id = _int_id(payload, "connection_id")
    if not connection_id:
        raise ValueError("connection_id is required")
    existing = session.get(SupermarketConnection, connection_id)
    if not _connection_is_operable(existing, user):
        raise ValueError("Connection not found")
    connection = delete_supermarket_connection(session, connection_id, user_id=user_id)
    if connection is None:
        raise ValueError("Connection not found")
    return {"deleted": True, "id": connection_id}


def _handle_supermarket_search(payload, session, *, user, now, user_id):
    store_key = (payload.get("store") or "intermarche").lower()
    if store_key not in ("intermarche", "carrefour", "leclerc", "auchan"):
        raise ValueError(
            "supermarket.search supports 'intermarche', 'carrefour', 'leclerc' "
            "or 'auchan'."
        )
    store_enum = SupermarketStore(store_key)
    queries = payload.get("queries")
    if isinstance(queries, str):
        queries = [queries]
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be a non-empty list")
    max_results = _clamp_int(payload.get("max_results"), default=10, minimum=1, maximum=30)
    promotions_only = _as_bool(payload.get("promotions_only"), default=False)
    try:
        results = asyncio.run(
            fetch_search_results(
                store=store_enum,
                queries=[str(query).strip() for query in queries if str(query).strip()],
                max_results=max_results,
                promotions_only=promotions_only,
                session=session,
                user_id=user_id,
            )
        )
    except RuntimeError as exc:
        raise ValueError(f"supermarket.search failed: {exc}") from exc
    saved = upsert_search_cache(session, store_enum, results)
    return {"results": [row.model_dump(mode="json") for row in saved]}


def _handle_supermarket_list_offering_contexts(payload, session, *, user, now, user_id):
    zipcode = str(payload.get("zipcode") or "").strip()
    city = str(payload.get("city") or "").strip()
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    if not zipcode or not city:
        raise ValueError("zipcode and city are required")
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        raise ValueError("latitude and longitude are required numbers") from None

    cookies = load_active_cookies(session, SupermarketStore.AUCHAN) or load_auchan_cookies()
    try:
        contexts = asyncio.run(
            list_auchan_offering_contexts(
                zipcode=zipcode,
                city=city,
                latitude=latitude,
                longitude=longitude,
                country=str(payload.get("country") or "France"),
                cookies=cookies,
            )
        )
    except AuchanAuthError as exc:
        raise ValueError(f"supermarket.list_offering_contexts failed: {exc}") from exc
    except RuntimeError as exc:
        raise ValueError(f"supermarket.list_offering_contexts failed: {exc}") from exc
    return {"contexts": contexts}


def _handle_supermarket_select_auchan_store(payload, session, *, user, now, user_id):
    seller_id = str(payload.get("seller_id") or "").strip()
    store_reference = str(payload.get("store_reference") or "").strip()
    store_label = str(payload.get("store_label") or "").strip()
    if not seller_id or not store_reference or not store_label:
        raise ValueError("seller_id, store_reference and store_label are required")

    cookies = load_active_cookies(session, SupermarketStore.AUCHAN) or load_auchan_cookies()
    context = AuchanStoreContext(
        seller_id=seller_id,
        store_reference=store_reference,
        channel=str(payload.get("channel") or "PICK_UP"),
        zipcode=payload.get("zipcode"),
        city=payload.get("city"),
        country=payload.get("country") or "France",
        latitude=_opt_float(payload.get("latitude")),
        longitude=_opt_float(payload.get("longitude")),
    )
    try:
        journey = asyncio.run(select_auchan_store(context, cookies=cookies))
    except AuchanAuthError as exc:
        raise ValueError(f"supermarket.select_auchan_store failed: {exc}") from exc
    except RuntimeError as exc:
        raise ValueError(f"supermarket.select_auchan_store failed: {exc}") from exc

    selection = upsert_selected_store(
        session,
        SupermarketStore.AUCHAN,
        external_store_id=seller_id,
        store_label=store_label,
        location_label=payload.get("location_label"),
        raw_payload={
            "store_reference": store_reference,
            "channel": context.channel,
            "zipcode": context.zipcode,
            "city": context.city,
            "country": context.country,
            "latitude": context.latitude,
            "longitude": context.longitude,
            "journey_id": journey.get("id"),
        },
    )
    return {
        "selection": {
            "external_store_id": selection.external_store_id,
            "store_label": selection.store_label,
            "location_label": selection.location_label,
            "updated_at": selection.updated_at.isoformat(),
        }
    }


def _opt_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _handle_grocery_list_items(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=500)
    statement = select(GroceryItem).where(GroceryItem.user_id == user_id).order_by(GroceryItem.checked.asc(), GroceryItem.priority.asc()).limit(limit)
    if payload.get("checked") is not None:
        statement = statement.where(GroceryItem.checked == _as_bool(payload.get("checked")))

    items = session.exec(statement).all()
    return {"items": [item.model_dump(mode="json") for item in items]}


def _handle_grocery_update_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(GroceryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")

    was_checked = item.checked
    patch = GroceryItemUpdate.model_validate({k: v for k, v in payload.items() if k != "item_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No grocery fields to update")

    apply_updates(item, updates, touch=True)
    item = save(session, item)
    pantry_sync = None
    if not was_checked and item.checked:
        pantry_sync = sync_checked_grocery_item_to_pantry(session, item, user_id=user_id)
        session.refresh(item)
    return {"item": item.model_dump(mode="json"), "pantry_sync": pantry_sync}


def _handle_grocery_check_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    checked = _as_bool(payload.get("checked"), default=True)
    item = session.get(GroceryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")
    was_checked = item.checked
    item.checked = checked
    item.updated_at = now
    item = save(session, item)
    pantry_sync = None
    if not was_checked and item.checked:
        pantry_sync = sync_checked_grocery_item_to_pantry(session, item, user_id=user_id)
        session.refresh(item)
    return {"item": item.model_dump(mode="json"), "pantry_sync": pantry_sync}


def _handle_grocery_delete_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(GroceryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")
    sync_rows = session.exec(
        select(GroceryPantrySync).where(GroceryPantrySync.grocery_item_id == item_id)
    ).all()
    for row in sync_rows:
        session.delete(row)
    if sync_rows:
        session.commit()
    delete(session, item)
    return {"ok": True, "deleted_id": item_id}


def _handle_video_fetch(payload, session, *, user, now, user_id):
    url = str(payload.get("url") or "").strip()
    if not url:
      raise ValueError("url is required")
    return {"video": extract_video_source(url).model_dump(mode="json")}


def _handle_recipe_add(payload, session, *, user, now, user_id):
    data = RecipeCreate.model_validate(payload)
    recipe = Recipe(
        name=data.name,
        description=data.description,
        instructions=data.instructions,
        steps=data.steps,
        utensils=data.utensils,
        prep_minutes=data.prep_minutes,
        cook_minutes=data.cook_minutes,
        servings=data.servings,
        tags=data.tags,
        source_url=data.source_url,
        source_platform=data.source_platform,
        source_title=data.source_title,
        source_description=data.source_description,
        source_transcript=data.source_transcript,
        user_id=user_id,
    )
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    for ing in data.ingredients:
        ingredient = RecipeIngredient(recipe_id=recipe.id, **resolve_recipe_ingredient_fields(session, ing))
        session.add(ingredient)
    session.commit()

    recipe = session.get(Recipe, recipe.id)
    return {"recipe": build_recipe_read(session, recipe).model_dump(mode="json")}


def _handle_recipe_update(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")

    patch = RecipeUpdate.model_validate({k: v for k, v in payload.items() if k != "recipe_id"})
    updates = patch.model_dump(exclude_unset=True)
    ingredients = updates.pop("ingredients", None)

    for key, value in updates.items():
        setattr(recipe, key, value)
    recipe.updated_at = now
    session.add(recipe)
    session.commit()

    if ingredients is not None:
        existing = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)).all()
        for row in existing:
            session.delete(row)
        session.commit()
        for ing in ingredients:
            ingredient = RecipeIngredient(recipe_id=recipe.id, **resolve_recipe_ingredient_fields(session, ing))
            session.add(ingredient)
        recipe.updated_at = now
        session.add(recipe)
        session.commit()

    session.refresh(recipe)
    return {"recipe": build_recipe_read(session, recipe).model_dump(mode="json")}


def _handle_recipe_list(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=20, minimum=1, maximum=100)
    recipes = session.exec(
        select(Recipe)
        .where(Recipe.user_id == user_id)
        .order_by(Recipe.created_at.desc())
        .limit(limit)
    ).all()
    data = [build_recipe_read(session, recipe).model_dump(mode="json") for recipe in recipes]
    return {"recipes": data}


def _handle_recipe_get(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    return {"recipe": build_recipe_read(session, recipe).model_dump(mode="json")}


def _handle_recipe_confirm_cooked(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    servings_override = None
    if payload.get("servings_override") is not None:
        try:
            servings_override = int(payload["servings_override"])
        except (TypeError, ValueError) as exc:
            raise ValueError("servings_override must be an integer") from exc
    result = confirm_recipe_cooked(session, recipe, servings_override, payload.get("note"), user_id=user_id)
    return {
        "recipe_id": recipe.id,
        "recipe_name": recipe.name,
        "cooked_at": result.get("confirmed_at"),
        "note": result.get("note"),
        "missing_ingredients": [item.model_dump(mode="json") for item in result.get("missing_ingredients", [])],
        "pantry_consumption": result.get("pantry_consumption", []),
        "meal_plan_id": result.get("meal_plan_id"),
        "already_confirmed": bool(result.get("already_confirmed")),
    }


def _handle_recipe_unconfirm_cooked(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    result = unconfirm_recipe_cooked(session, recipe, user_id=user_id)
    return {
        "recipe_id": recipe.id,
        "recipe_name": recipe.name,
        "already_unconfirmed": bool(result.get("already_unconfirmed")),
        "previously_confirmed_at": result.get("previously_confirmed_at"),
        "note": result.get("note"),
        "pantry_restore": result.get("pantry_restore", []),
    }


def _handle_recipe_delete(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    ingredient_rows = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)).all()
    for row in ingredient_rows:
        session.delete(row)
    if ingredient_rows:
        session.commit()

    meal_plans = session.exec(
        select(MealPlan).where(MealPlan.recipe_id == recipe.id, MealPlan.user_id == user_id)
    ).all()
    for plan in meal_plans:
        confirmation = session.exec(
            select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == plan.id)
        ).first()
        if confirmation:
            session.delete(confirmation)
        session.delete(plan)
    if meal_plans:
        session.commit()

    session.delete(recipe)
    session.commit()
    return {"ok": True, "deleted_id": recipe_id}


def _handle_meal_plan_add(payload, session, *, user, now, user_id):
    data = MealPlanCreate.model_validate(payload)
    _get_owned_recipe(session, data.recipe_id, user_id)

    planned_at = _resolve_meal_planned_at(payload)
    planned_for = _parse_date(payload.get("planned_for"), "planned_for") or planned_at.date()
    slot = data.slot
    validate_meal_plan_slot_free(
        session,
        user_id=user_id,
        planned_for=planned_for,
        slot=slot,
    )
    plan = MealPlan(**data.model_dump(exclude={"planned_at"}), planned_at=planned_at, user_id=user_id)
    if plan.planned_for is None:
        plan.planned_for = planned_at.date()
    session.add(plan)
    session.commit()
    session.refresh(plan)

    if plan.auto_add_missing_ingredients:
        sync_meal_plan_to_grocery(session, plan, user_id=user_id)
    return {"meal_plan": build_meal_plan_read(session, plan, user_id=user_id).model_dump(mode="json")}


def _handle_meal_plan_list(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=400)
    date_from = _parse_date(payload.get("date_from"), "date_from") if payload.get("date_from") else None
    date_to = _parse_date(payload.get("date_to"), "date_to") if payload.get("date_to") else None
    slot = MealSlot(payload.get("slot")) if payload.get("slot") else None
    plans = visible_meal_plans(
        session,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        slot=slot,
        limit=limit,
    )
    return {
        "meal_plans": [
            read.model_dump(mode="json") for read in build_meal_plan_reads(session, plans, user_id=user_id)
        ]
    }


def _handle_meal_plan_update(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    patch = MealPlanUpdate.model_validate({k: v for k, v in payload.items() if k != "meal_plan_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No meal plan fields to update")
    if "recipe_id" in updates:
        _get_owned_recipe(session, updates["recipe_id"], user_id)

    next_planned_at = _resolve_meal_planned_at({**payload, **updates}, current=plan.planned_at)
    next_planned_for = updates.get("planned_for", plan.planned_for)
    if next_planned_for is None:
        next_planned_for = next_planned_at.date()
    next_slot = updates.get("slot", plan.slot)
    validate_meal_plan_slot_free(
        session,
        user_id=user_id,
        planned_for=next_planned_for,
        slot=next_slot,
        exclude_plan_id=plan.id,
    )

    reset_cook_confirmation = (
        ("planned_at" in updates and updates.get("planned_at") != plan.planned_at)
        or
        ("planned_for" in updates and updates.get("planned_for") != plan.planned_for)
        or ("slot" in updates and updates.get("slot") != plan.slot)
        or ("recipe_id" in updates and updates.get("recipe_id") != plan.recipe_id)
        or ("servings_override" in updates and updates.get("servings_override") != plan.servings_override)
    )

    for key, value in updates.items():
        setattr(plan, key, value)
    plan.planned_at = next_planned_at
    plan.planned_for = next_planned_for
    if reset_cook_confirmation:
        reset_meal_plan_cook_confirmation(session, plan)
    plan.updated_at = now
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return {"meal_plan": build_meal_plan_read(session, plan, user_id=user_id).model_dump(mode="json")}


def _handle_meal_plan_delete(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    confirmation = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == plan.id)
    ).first()
    if confirmation:
        session.delete(confirmation)
        session.commit()
    session.delete(plan)
    session.commit()
    return {"ok": True, "deleted_id": meal_plan_id}


def _handle_meal_plan_sync_groceries(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    created, missing = sync_meal_plan_to_grocery(session, plan, user_id=user_id)
    return {
        "meal_plan_id": meal_plan_id,
        "created_grocery_items": created,
        "missing_ingredients": [item.model_dump(mode="json") for item in missing],
    }


def _handle_meal_plan_confirm_cooked(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    result = confirm_meal_plan_cooked(session, plan, note=payload.get("note"), user_id=user_id)
    return {
        "meal_plan_id": meal_plan_id,
        "already_confirmed": bool(result.get("already_confirmed")),
        "confirmed_at": result.get("confirmed_at"),
        "note": result.get("note"),
        "pantry_consumption": result.get("pantry_consumption", []),
    }


def _handle_meal_plan_log_cooked(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    _get_owned_recipe(session, recipe_id, user_id)
    cooked_at = _parse_datetime(payload.get("cooked_at"), "cooked_at") or now
    plan = MealPlan(
        recipe_id=recipe_id,
        planned_at=cooked_at,
        planned_for=cooked_at.date(),
        servings_override=payload.get("servings_override"),
        note=payload.get("note") or "cooked without explicit planning",
        auto_add_missing_ingredients=False,
        user_id=user_id,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    result = confirm_meal_plan_cooked(session, plan, note=payload.get("note"), user_id=user_id)
    return {
        "meal_plan": build_meal_plan_read(session, plan, user_id=user_id).model_dump(mode="json"),
        "confirmation": result,
    }


def _handle_meal_plan_unconfirm_cooked(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    result = unconfirm_meal_plan_cooked(session, plan, user_id=user_id)
    return {
        "meal_plan_id": meal_plan_id,
        "already_unconfirmed": bool(result.get("already_unconfirmed")),
        "previously_confirmed_at": result.get("previously_confirmed_at"),
        "note": result.get("note"),
        "pantry_restore": result.get("pantry_restore", []),
    }


def _handle_calendar_add_item(payload, session, *, user, now, user_id):
    data = CalendarItemCreate.model_validate(payload)
    if data.end_at <= data.start_at:
        raise ValueError("end_at must be after start_at")
    validate_calendar_slot_free(session, data.start_at, data.end_at)
    item = CalendarItem(
        **data.model_dump(),
        source=CalendarSource.MANUAL,
        generated=False,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"item": build_calendar_item_read(item).model_dump(mode="json", by_alias=True)}


def _handle_calendar_list_items(payload, session, *, user, now, user_id):
    sync_generated_calendar_items(session)
    limit = _clamp_int(payload.get("limit"), default=500, minimum=1, maximum=2000)
    statement = select(CalendarItem).order_by(CalendarItem.start_at.asc()).limit(limit)
    if payload.get("from_at"):
        statement = statement.where(CalendarItem.start_at >= _parse_datetime(payload.get("from_at"), "from_at"))
    if payload.get("to_at"):
        statement = statement.where(CalendarItem.start_at <= _parse_datetime(payload.get("to_at"), "to_at"))
    if payload.get("category"):
        statement = statement.where(CalendarItem.category == CalendarCategory(payload.get("category")))
    if payload.get("source"):
        statement = statement.where(CalendarItem.source == CalendarSource(payload.get("source")))
    if payload.get("include_completed") is not None and not _as_bool(payload.get("include_completed"), default=True):
        statement = statement.where(CalendarItem.completed.is_(False))
    if payload.get("generated_only") is not None:
        statement = statement.where(CalendarItem.generated == _as_bool(payload.get("generated_only"), default=False))

    rows = session.exec(statement).all()
    return {"items": [build_calendar_item_read(item).model_dump(mode="json", by_alias=True) for item in rows]}


def _handle_calendar_update_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(CalendarItem, item_id)
    if not item:
        raise ValueError("item_id not found")
    if item.generated:
        raise ValueError("Generated calendar items must be updated from their source module")
    patch = CalendarItemUpdate.model_validate({k: v for k, v in payload.items() if k != "item_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No calendar fields to update")
    for key, value in updates.items():
        setattr(item, key, value)
    if item.end_at <= item.start_at:
        raise ValueError("end_at must be after start_at")
    validate_calendar_slot_free(
        session,
        item.start_at,
        item.end_at,
        ignore_calendar_item_id=item.id,
    )
    item.updated_at = now
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"item": build_calendar_item_read(item).model_dump(mode="json", by_alias=True)}


def _handle_calendar_delete_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(CalendarItem, item_id)
    if not item:
        raise ValueError("item_id not found")
    if item.generated:
        raise ValueError("Generated calendar items must be deleted from their source module")
    session.delete(item)
    session.commit()
    return {"ok": True, "deleted_id": item_id}


def _handle_calendar_agenda(payload, session, *, user, now, user_id):
    sync_generated_calendar_items(session)
    day_value = _parse_date(payload.get("day"), "day") or now.date()
    day_start = datetime.combine(day_value, datetime.min.time()).replace(tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    include_completed = _as_bool(payload.get("include_completed"), default=False)
    statement = select(CalendarItem).where(CalendarItem.start_at >= day_start, CalendarItem.start_at < day_end).order_by(CalendarItem.start_at.asc())
    if not include_completed:
        statement = statement.where(CalendarItem.completed.is_(False))
    rows = session.exec(statement).all()
    return {"items": [build_calendar_item_read(item).model_dump(mode="json", by_alias=True) for item in rows]}


def _handle_calendar_sync(payload, session, *, user, now, user_id):
    synced, removed, by_source = sync_generated_calendar_items(session)
    return {"synced": synced, "removed": removed, "generated_by_source": by_source, "synced_at": now.isoformat()}


def _handle_calendar_due_reminders(payload, session, *, user, now, user_id):
    sync_generated_calendar_items(session)
    within_minutes = _clamp_int(payload.get("within_minutes"), default=30, minimum=1, maximum=1440)
    reminders = list_due_reminders(session, within_minutes=within_minutes)
    return {"reminders": [entry.model_dump(mode="json") for entry in reminders]}


def _handle_calendar_ack_reminder(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(CalendarItem, item_id)
    if not item:
        raise ValueError("item_id not found")
    item.last_notified_at = now
    item.updated_at = now
    session.add(item)
    session.commit()
    return {"ok": True, "item_id": item_id, "ack_at": now.isoformat()}


def _handle_habit_create(payload, session, *, user, now, user_id):
    data = HabitCreate.model_validate(payload)
    habit = Habit(**data.model_dump())
    validate_habit_schedule_free(session, habit)
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return {"habit": habit.model_dump(mode="json")}


def _handle_habit_update(payload, session, *, user, now, user_id):
    habit_id = _int_id(payload, "habit_id")
    habit = session.get(Habit, habit_id)
    if not habit:
        raise ValueError("habit_id not found")

    patch = HabitUpdate.model_validate({k: v for k, v in payload.items() if k != "habit_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No habit fields to update")

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

    validate_habit_schedule_free(session, habit, ignore_habit_id=habit.id)

    habit.updated_at = now
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return {"habit": habit.model_dump(mode="json")}


def _handle_habit_list(payload, session, *, user, now, user_id):
    active_only = _as_bool(payload.get("active_only"), default=True)
    statement = select(Habit).order_by(Habit.created_at.desc())
    if active_only:
        statement = statement.where(Habit.active.is_(True))
    habits = session.exec(statement).all()
    return {"habits": [habit.model_dump(mode="json") for habit in habits]}


def _handle_habit_set_active(payload, session, *, user, now, user_id):
    habit_id = _int_id(payload, "habit_id")
    active = _as_bool(payload.get("active"), default=True)
    habit = session.get(Habit, habit_id)
    if not habit:
        raise ValueError("habit_id not found")
    habit.active = active
    habit.updated_at = now
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return {"habit": habit.model_dump(mode="json")}


def _handle_habit_log(payload, session, *, user, now, user_id):
    habit_id = _int_id(payload, "habit_id")
    habit = session.get(Habit, habit_id)
    if not habit:
        raise ValueError("habit_id not found")

    log = create(
        session,
        HabitLog(
            habit_id=habit_id,
            value=int(payload.get("value", 1)),
            note=payload.get("note"),
        ),
    )

    streak = update_habit_streak(session, habit_id)
    return {"log": log.model_dump(mode="json"), "streak": streak}


def _handle_habit_list_logs(payload, session, *, user, now, user_id):
    habit_id = _int_id(payload, "habit_id")
    habit = session.get(Habit, habit_id)
    if not habit:
        raise ValueError("habit_id not found")

    limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=500)
    logs = session.exec(
        select(HabitLog)
        .where(HabitLog.habit_id == habit_id)
        .order_by(HabitLog.logged_at.desc())
        .limit(limit)
    ).all()
    return {"logs": [log.model_dump(mode="json") for log in logs]}


def _handle_goal_create(payload, session, *, user, now, user_id):
    data = GoalCreate.model_validate(payload)
    goal = create(session, Goal(**data.model_dump(), user_id=user_id))
    return {"goal": goal.model_dump(mode="json")}


def _handle_goal_list(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=300)
    statement = (
        select(Goal)
        .where(Goal.user_id == user_id)
        .order_by(Goal.created_at.desc())
        .limit(limit)
    )
    if payload.get("status"):
        statement = statement.where(Goal.status == GoalStatus(payload["status"]))
    goals = session.exec(statement).all()
    return {"goals": [goal.model_dump(mode="json") for goal in goals]}


def _get_owned_goal(session, user_id: int, goal_id: int) -> Goal:
    goal = session.get(Goal, goal_id)
    if not goal or goal.user_id != user_id:
        raise ValueError("goal_id not found")
    return goal


def _handle_goal_get(payload, session, *, user, now, user_id):
    goal_id = _int_id(payload, "goal_id")
    goal = _get_owned_goal(session, user_id, goal_id)
    return {"goal": goal.model_dump(mode="json")}


def _handle_goal_update(payload, session, *, user, now, user_id):
    goal_id = _int_id(payload, "goal_id")
    goal = _get_owned_goal(session, user_id, goal_id)

    patch = GoalUpdate.model_validate({k: v for k, v in payload.items() if k != "goal_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No goal fields to update")

    apply_updates(goal, updates, touch=True)
    goal = save(session, goal)
    return {"goal": goal.model_dump(mode="json")}


def _handle_goal_add_milestone(payload, session, *, user, now, user_id):
    goal_id = _int_id(payload, "goal_id")
    goal = _get_owned_goal(session, user_id, goal_id)

    data = GoalMilestoneCreate.model_validate({k: v for k, v in payload.items() if k != "goal_id"})
    milestone = create(session, GoalMilestone(goal_id=goal.id, **data.model_dump()))
    return {"milestone": milestone.model_dump(mode="json")}


def _handle_goal_list_milestones(payload, session, *, user, now, user_id):
    goal_id = _int_id(payload, "goal_id")
    goal = _get_owned_goal(session, user_id, goal_id)

    limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=500)
    milestones = session.exec(
        select(GoalMilestone)
        .where(GoalMilestone.goal_id == goal.id)
        .order_by(GoalMilestone.created_at.desc())
        .limit(limit)
    ).all()
    return {"milestones": [item.model_dump(mode="json") for item in milestones]}


def _handle_goal_update_milestone(payload, session, *, user, now, user_id):
    goal_id = _int_id(payload, "goal_id")
    milestone_id = _int_id(payload, "milestone_id")
    goal = _get_owned_goal(session, user_id, goal_id)

    milestone = session.get(GoalMilestone, milestone_id)
    if not milestone or milestone.goal_id != goal.id:
        raise ValueError("milestone_id not found")

    patch = GoalMilestoneUpdate.model_validate(
        {k: v for k, v in payload.items() if k not in {"goal_id", "milestone_id"}}
    )
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No milestone fields to update")

    apply_updates(milestone, updates)
    if patch.completed is True and milestone.completed_at is None:
        milestone.completed_at = now
    if patch.completed is False:
        milestone.completed_at = None

    milestone = save(session, milestone)
    return {"milestone": milestone.model_dump(mode="json")}


def _handle_event_create(payload, session, *, user, now, user_id):
    data = EventCreate.model_validate(payload)
    if data.end_at <= data.start_at:
        raise ValueError("end_at must be after start_at")
    validate_calendar_slot_free(
        session,
        data.start_at,
        data.end_at,
        source=CalendarSource.EVENT,
    )
    event = CalendarEvent(**data.model_dump())
    session.add(event)
    session.commit()
    session.refresh(event)
    return {"event": event.model_dump(mode="json")}


def _handle_event_list(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=500)
    statement = select(CalendarEvent).order_by(CalendarEvent.start_at.asc()).limit(limit)
    from_at = _parse_datetime(payload.get("from_at"), "from_at")
    to_at = _parse_datetime(payload.get("to_at"), "to_at")
    if from_at:
        statement = statement.where(CalendarEvent.start_at >= from_at)
    if to_at:
        statement = statement.where(CalendarEvent.start_at <= to_at)
    if payload.get("type"):
        statement = statement.where(CalendarEvent.type == EventType(payload["type"]))

    events = session.exec(statement).all()
    return {"events": [event.model_dump(mode="json") for event in events]}


def _handle_event_upcoming(payload, session, *, user, now, user_id):
    days = _clamp_int(payload.get("days"), default=7, minimum=1, maximum=365)
    event_type = EventType(payload["type"]) if payload.get("type") else None
    events = list_upcoming_events(session, days=days, event_type=event_type)
    return {"events": [event.model_dump(mode="json") for event in events]}


def _handle_event_get(payload, session, *, user, now, user_id):
    event_id = _int_id(payload, "event_id")
    event = session.get(CalendarEvent, event_id)
    if not event:
        raise ValueError("event_id not found")
    return {"event": event.model_dump(mode="json")}


def _handle_event_update(payload, session, *, user, now, user_id):
    event_id = _int_id(payload, "event_id")
    event = session.get(CalendarEvent, event_id)
    if not event:
        raise ValueError("event_id not found")

    patch = EventUpdate.model_validate({k: v for k, v in payload.items() if k != "event_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No event fields to update")

    for key, value in updates.items():
        setattr(event, key, value)
    if event.end_at <= event.start_at:
        raise ValueError("end_at must be after start_at")
    validate_calendar_slot_free(
        session,
        event.start_at,
        event.end_at,
        source=CalendarSource.EVENT,
        source_ref_id=event.id,
    )
    event.updated_at = now

    session.add(event)
    session.commit()
    session.refresh(event)
    return {"event": event.model_dump(mode="json")}


def _handle_event_delete(payload, session, *, user, now, user_id):
    event_id = _int_id(payload, "event_id")
    event = session.get(CalendarEvent, event_id)
    if not event:
        raise ValueError("event_id not found")
    delete(session, event)
    return {"ok": True, "deleted_id": event_id}


def _handle_subscription_create(payload, session, *, user, now, user_id):
    data = SubscriptionCreate.model_validate(payload)
    slot_start = _subscription_slot_start(data.next_due_date)
    validate_calendar_slot_free(
        session,
        slot_start,
        slot_start + timedelta(minutes=30),
        source=CalendarSource.SUBSCRIPTION,
    )
    subscription = Subscription(**data.model_dump(), user_id=user_id)
    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return {"subscription": subscription.model_dump(mode="json")}


def _handle_subscription_list(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=500)
    active_only = _as_bool(payload.get("active_only"), default=True)
    statement = (
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .order_by(Subscription.next_due_date.asc())
        .limit(limit)
    )
    if active_only:
        statement = statement.where(Subscription.active.is_(True))
    subscriptions = session.exec(statement).all()
    return {"subscriptions": [item.model_dump(mode="json") for item in subscriptions]}


def _get_owned_subscription(session, user_id: int, subscription_id: int) -> Subscription:
    subscription = session.get(Subscription, subscription_id)
    if not subscription or subscription.user_id != user_id:
        raise ValueError("subscription_id not found")
    return subscription


def _handle_subscription_get(payload, session, *, user, now, user_id):
    subscription_id = _int_id(payload, "subscription_id")
    subscription = _get_owned_subscription(session, user_id, subscription_id)
    return {"subscription": subscription.model_dump(mode="json")}


def _handle_subscription_update(payload, session, *, user, now, user_id):
    subscription_id = _int_id(payload, "subscription_id")
    subscription = _get_owned_subscription(session, user_id, subscription_id)

    patch = SubscriptionUpdate.model_validate({k: v for k, v in payload.items() if k != "subscription_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No subscription fields to update")

    next_due_date = updates.get("next_due_date", subscription.next_due_date)
    slot_start = _subscription_slot_start(next_due_date)
    validate_calendar_slot_free(
        session,
        slot_start,
        slot_start + timedelta(minutes=30),
        source=CalendarSource.SUBSCRIPTION,
        source_ref_id=subscription.id,
    )

    for key, value in updates.items():
        setattr(subscription, key, value)
    subscription.updated_at = now

    session.add(subscription)
    session.commit()
    session.refresh(subscription)
    return {"subscription": subscription.model_dump(mode="json")}


def _handle_subscription_upcoming(payload, session, *, user, now, user_id):
    days = _clamp_int(payload.get("days"), default=30, minimum=1, maximum=365)
    subscriptions = list_upcoming_subscriptions(session, days=days, user_id=user_id)
    return {"subscriptions": [item.model_dump(mode="json") for item in subscriptions]}


def _handle_subscription_projection(payload, session, *, user, now, user_id):
    currency = payload.get("currency", "EUR")
    projection = build_subscription_projection(session, currency=currency, user_id=user_id)
    return {"projection": projection.model_dump(mode="json")}


def _handle_patrimony_overview(payload, session, *, user, now, user_id):
    accounts = session.exec(
        select(Account)
        .where(Account.user_id == user_id, Account.is_active.is_(True))
        .order_by(Account.name.asc())
    ).all()
    goals = session.exec(
        select(SavingsGoal)
        .where(SavingsGoal.user_id == user_id)
        .order_by(SavingsGoal.target_date.asc())
    ).all()
    accounts_by_id = {account.id: account for account in accounts if account.id is not None}
    return {
        "overview": {
            "net_worth": sum(account.balance for account in accounts),
            "currency": "EUR",
            "accounts": [_build_account_read_payload(account) for account in accounts],
            "goals": [
                _build_savings_goal_read_payload(goal, accounts_by_id) for goal in goals
            ],
        }
    }


def _handle_patrimony_list_accounts(payload, session, *, user, now, user_id):
    active_only = _as_bool(payload.get("active_only"), default=True)
    statement = select(Account).where(Account.user_id == user_id).order_by(Account.name.asc())
    if active_only:
        statement = statement.where(Account.is_active.is_(True))
    rows = session.exec(statement).all()
    return {"accounts": [_build_account_read_payload(row) for row in rows]}


def _handle_patrimony_add_account(payload, session, *, user, now, user_id):
    data = AccountCreate.model_validate(payload)
    row = create(session, Account(**data.model_dump(), user_id=user_id))
    return {"account": _build_account_read_payload(row)}


def _handle_patrimony_update_account(payload, session, *, user, now, user_id):
    account_id = _int_id(payload, "account_id")
    row = session.get(Account, account_id)
    if not row or row.user_id != user_id:
        raise ValueError("account_id not found")
    patch = AccountUpdate.model_validate(
        {k: v for k, v in payload.items() if k != "account_id"}
    )
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No patrimony account fields to update")
    apply_updates(row, updates, touch=True)
    row = save(session, row)
    return {"account": _build_account_read_payload(row)}


def _handle_patrimony_delete_account(payload, session, *, user, now, user_id):
    account_id = _int_id(payload, "account_id")
    row = session.get(Account, account_id)
    if not row or row.user_id != user_id:
        raise ValueError("account_id not found")
    delete(session, row)
    return {"ok": True, "deleted_id": account_id}


def _scoped_accounts_by_id(session, user_id: int) -> dict[int, Account]:
    rows = session.exec(
        select(Account).where(Account.user_id == user_id)
    ).all()
    return {account.id: account for account in rows if account.id is not None}


def _handle_patrimony_list_goals(payload, session, *, user, now, user_id):
    goals = session.exec(
        select(SavingsGoal)
        .where(SavingsGoal.user_id == user_id)
        .order_by(SavingsGoal.target_date.asc())
    ).all()
    accounts_by_id = _scoped_accounts_by_id(session, user_id)
    return {
        "goals": [
            _build_savings_goal_read_payload(goal, accounts_by_id) for goal in goals
        ]
    }


def _handle_patrimony_add_goal(payload, session, *, user, now, user_id):
    data = SavingsGoalCreate.model_validate(payload)
    row = create(session, SavingsGoal(**data.model_dump(), user_id=user_id))
    accounts_by_id = _scoped_accounts_by_id(session, user_id)
    return {"goal": _build_savings_goal_read_payload(row, accounts_by_id)}


def _handle_patrimony_update_goal(payload, session, *, user, now, user_id):
    goal_id = _int_id(payload, "goal_id")
    row = session.get(SavingsGoal, goal_id)
    if not row or row.user_id != user_id:
        raise ValueError("goal_id not found")
    patch = SavingsGoalUpdate.model_validate(
        {k: v for k, v in payload.items() if k != "goal_id"}
    )
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No patrimony goal fields to update")
    apply_updates(row, updates, touch=True)
    row = save(session, row)
    accounts_by_id = _scoped_accounts_by_id(session, user_id)
    return {"goal": _build_savings_goal_read_payload(row, accounts_by_id)}


def _handle_patrimony_delete_goal(payload, session, *, user, now, user_id):
    goal_id = _int_id(payload, "goal_id")
    row = session.get(SavingsGoal, goal_id)
    if not row or row.user_id != user_id:
        raise ValueError("goal_id not found")
    delete(session, row)
    return {"ok": True, "deleted_id": goal_id}


def _handle_pantry_add_item(payload, session, *, user, now, user_id):
    data = PantryItemCreate.model_validate(payload)
    item = create(session, PantryItem(**data.model_dump(), user_id=user_id))
    return {"item": item.model_dump(mode="json")}


def _handle_pantry_list_items(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=500, minimum=1, maximum=1000)
    low_stock_only = _as_bool(payload.get("low_stock_only"), default=False)
    expiring_in_days = payload.get("expiring_in_days")

    statement = (
        select(PantryItem)
        .where(PantryItem.user_id == user_id)
        .order_by(PantryItem.updated_at.desc())
        .limit(limit)
    )
    if low_stock_only:
        statement = statement.where(PantryItem.quantity <= PantryItem.min_quantity)
    if expiring_in_days is not None:
        days = _clamp_int(expiring_in_days, default=7, minimum=1, maximum=3650)
        until = date.today() + timedelta(days=days)
        statement = statement.where(PantryItem.expires_at.is_not(None), PantryItem.expires_at <= until)

    items = session.exec(statement).all()
    return {"items": [item.model_dump(mode="json") for item in items]}


def _handle_pantry_update_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(PantryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")

    patch = PantryItemUpdate.model_validate({k: v for k, v in payload.items() if k != "item_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No pantry fields to update")

    apply_updates(item, updates, touch=True)
    item = save(session, item)
    return {"item": item.model_dump(mode="json")}


def _handle_pantry_consume_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    amount = float(payload.get("amount", 0))
    if amount <= 0:
        raise ValueError("amount must be > 0")

    item = session.get(PantryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")

    item.quantity = max(0.0, item.quantity - amount)
    item.updated_at = now
    item = save(session, item)
    return {"item": item.model_dump(mode="json")}


def _handle_pantry_delete_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(PantryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")
    sync_rows = session.exec(
        select(GroceryPantrySync).where(GroceryPantrySync.pantry_item_id == item_id)
    ).all()
    for row in sync_rows:
        session.delete(row)
    if sync_rows:
        session.commit()
    delete(session, item)
    return {"ok": True, "deleted_id": item_id}


def _handle_pantry_overview(payload, session, *, user, now, user_id):
    days = _clamp_int(payload.get("days"), default=7, minimum=1, maximum=365)
    overview = build_pantry_overview(session, days=days, user_id=user_id)
    return {"overview": overview.model_dump(mode="json")}


def _handle_note_create(payload, session, *, user, now, user_id):
    data = NoteCreate.model_validate(payload)
    note = create(session, Note(**data.model_dump(), user_id=user_id))
    return {"note": note.model_dump(mode="json")}


def _handle_note_list(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=300, minimum=1, maximum=1000)
    statement = (
        select(Note)
        .where(Note.user_id == user_id)
        .order_by(Note.pinned.desc(), Note.updated_at.desc())
        .limit(limit)
    )
    if payload.get("kind"):
        statement = statement.where(Note.kind == NoteKind(payload["kind"]))
    if payload.get("pinned") is not None:
        statement = statement.where(Note.pinned == _as_bool(payload.get("pinned")))

    notes = session.exec(statement).all()
    tag = payload.get("tag")
    if tag:
        notes = [note for note in notes if tag in note.tags]
    q = payload.get("q")
    if q:
        ql = str(q).lower()
        notes = [note for note in notes if ql in note.title.lower() or ql in note.content.lower()]

    return {"notes": [note.model_dump(mode="json") for note in notes]}


def _handle_note_get(payload, session, *, user, now, user_id):
    note_id = _int_id(payload, "note_id")
    note = _get_owned_note(session, note_id, user_id)
    return {"note": note.model_dump(mode="json")}


def _handle_note_update(payload, session, *, user, now, user_id):
    note_id = _int_id(payload, "note_id")
    note = _get_owned_note(session, note_id, user_id)

    patch = NoteUpdate.model_validate({k: v for k, v in payload.items() if k != "note_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No note fields to update")

    apply_updates(note, updates, touch=True)
    note = save(session, note)
    return {"note": note.model_dump(mode="json")}


def _handle_note_delete(payload, session, *, user, now, user_id):
    note_id = _int_id(payload, "note_id")
    note = _get_owned_note(session, note_id, user_id)

    delete(session, note)
    return {"ok": True, "deleted_id": note_id}


def _handle_note_journal(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=1000)
    statement = (
        select(Note)
        .where(Note.kind == NoteKind.JOURNAL, Note.user_id == user_id)
        .order_by(Note.created_at.desc())
        .limit(limit)
    )
    notes = session.exec(statement).all()

    from_date = _parse_date(payload.get("from_date"), "from_date")
    to_date = _parse_date(payload.get("to_date"), "to_date")
    if from_date:
        notes = [note for note in notes if note.created_at.date() >= from_date]
    if to_date:
        notes = [note for note in notes if note.created_at.date() <= to_date]

    return {"notes": [note.model_dump(mode="json") for note in notes]}


def _handle_dashboard_overview(payload, session, *, user, now, user_id):
    return {"overview": build_dashboard_overview(session, user_id=user_id).model_dump(mode="json")}


ACTION_CATALOG = [
    {"action": "task.create", "description": "Create a one-shot task. For a scheduled task, use due_at plus estimated_minutes. If the user wants a checklist or steps, store them in subtasks. Do not use calendar.add_item for normal tasks.", "input_schema": {"title": "string", "description": "string?", "subtasks": "[{id?, title, completed}]?", "schedule_mode": "none|once|daily|weekly?", "schedule_time": "HH:MM?", "schedule_weekday": "0=Monday..6=Sunday?", "due_at": "datetime?", "priority": "low|medium|high|urgent", "estimated_minutes": "int?", "tags": "string[]?"}, "handler": _handle_task_create},
    {"action": "task.list", "description": "List tasks with optional status filter", "input_schema": {"status": "todo|in_progress|done|blocked?", "only_open": "bool?", "limit": "int?"}, "handler": _handle_task_list},
    {"action": "task.update", "description": "Update an existing task. Use this to change title, description, checklist, timing, duration, or status. Keep task scheduling inside task.update, not calendar.update_item.", "input_schema": {"task_id": "int", "title": "string?", "description": "string?", "subtasks": "[{id?, title, completed}]?", "schedule_mode": "none|once|daily|weekly?", "schedule_time": "HH:MM?", "schedule_weekday": "0=Monday..6=Sunday?", "due_at": "datetime?", "priority": "low|medium|high|urgent?", "status": "todo|in_progress|done|blocked?", "estimated_minutes": "int?", "tags": "string[]?"}, "handler": _handle_task_update},
    {"action": "task.complete", "description": "Mark a task as done", "input_schema": {"task_id": "int"}, "handler": _handle_task_complete},
    {"action": "task.delete", "description": "Delete a task", "input_schema": {"task_id": "int"}, "handler": _handle_task_delete},
    {"action": "finance.add_transaction", "description": "Add an income or expense transaction", "input_schema": {"kind": "income|expense", "amount": "float", "currency": "string?", "category": "string", "note": "string?", "occurred_at": "datetime?", "is_recurring": "bool?"}, "handler": _handle_finance_add_transaction},
    {"action": "finance.list_transactions", "description": "List transactions", "input_schema": {"kind": "income|expense?", "year": "int?", "month": "int?", "limit": "int?"}, "handler": _handle_finance_list_transactions},
    {"action": "finance.create_budget", "description": "Create a monthly category budget", "input_schema": {"month": "YYYY-MM", "category": "string", "monthly_limit": "float", "currency": "string?", "alert_threshold": "float?"}, "handler": _handle_finance_create_budget},
    {"action": "finance.list_budgets", "description": "List budgets with optional month", "input_schema": {"month": "YYYY-MM?"}, "handler": _handle_finance_list_budgets},
    {"action": "finance.month_summary", "description": "Compute month financial summary", "input_schema": {"year": "int?", "month": "int?"}, "handler": _handle_finance_month_summary},
    {"action": "fitness.overview", "description": "Return the fitness dashboard overview", "input_schema": {}, "handler": _handle_fitness_overview},
    {"action": "fitness.list_sessions", "description": "List fitness sessions", "input_schema": {"limit": "int?"}, "handler": _handle_fitness_list_sessions},
    {"action": "fitness.create_session", "description": "Create a fitness session", "input_schema": {"title": "string", "session_type": "strength|cardio|mobility|recovery|mixed?", "planned_at": "datetime?", "duration_minutes": "int?", "exercises": "[{name, mode, reps, duration_minutes, note}|string]?", "note": "string?"}, "handler": _handle_fitness_create_session},
    {"action": "fitness.update_session", "description": "Update a fitness session", "input_schema": {"session_id": "int", "title": "string?", "session_type": "strength|cardio|mobility|recovery|mixed?", "planned_at": "datetime?", "duration_minutes": "int?", "exercises": "[{name, mode, reps, duration_minutes, note}|string]?", "note": "string?", "status": "planned|completed|skipped?", "actual_duration_minutes": "int?", "effort_rating": "int?", "calories_burned": "float?"}, "handler": _handle_fitness_update_session},
    {"action": "fitness.complete_session", "description": "Mark a fitness session as completed", "input_schema": {"session_id": "int", "note": "string?", "actual_duration_minutes": "int?", "effort_rating": "int?", "calories_burned": "float?"}, "handler": _handle_fitness_complete_session},
    {"action": "fitness.delete_session", "description": "Delete a fitness session", "input_schema": {"session_id": "int"}, "handler": _handle_fitness_delete_session},
    {"action": "fitness.list_measurements", "description": "List fitness measurements", "input_schema": {"limit": "int?"}, "handler": _handle_fitness_list_measurements},
    {"action": "fitness.add_measurement", "description": "Add a fitness measurement", "input_schema": {"recorded_at": "datetime?", "body_weight_kg": "float?", "body_fat_pct": "float?", "resting_hr": "int?", "sleep_hours": "float?", "steps": "int?", "note": "string?"}, "handler": _handle_fitness_add_measurement},
    {"action": "fitness.update_measurement", "description": "Update a fitness measurement", "input_schema": {"measurement_id": "int", "recorded_at": "datetime?", "body_weight_kg": "float?", "body_fat_pct": "float?", "resting_hr": "int?", "sleep_hours": "float?", "steps": "int?", "note": "string?"}, "handler": _handle_fitness_update_measurement},
    {"action": "fitness.delete_measurement", "description": "Delete a fitness measurement", "input_schema": {"measurement_id": "int"}, "handler": _handle_fitness_delete_measurement},
    {"action": "supermarket.list_stores", "description": "List supported supermarket stores and capabilities", "input_schema": {}, "handler": _handle_supermarket_list_stores},
    # ── Multi-account connections (cookies stored encrypted in DB) ──────────
    {"action": "supermarket.list_connections", "description": "List saved supermarket connections (cookie sets) across all stores. Each entry has an id, label, store, is_active flag and cookies_count. Multiple connections per store are allowed (e.g. user + spouse).", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan?"}, "handler": _handle_supermarket_list_connections},
    {"action": "supermarket.import_connection", "description": "Save a fresh cookie set (or best-effort credentials) for a supermarket. Used by the AdamHUB Connect Chrome extension after a successful login. `cookies` is the array dumped via chrome.cookies.getAll. Set activate=true to make this connection the default consumer for the store. `credentials` ({username, password}) is a best-effort fallback when the store has no captcha/2FA on programmatic login; cookies remain the reliable path.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan", "label": "string", "cookies": "object[]?", "credentials": "object?", "activate": "bool?", "connection_id": "int?"}, "handler": _handle_supermarket_import_connection},
    {"action": "supermarket.activate_connection", "description": "Switch the active connection for a store (search/cart/orders will use this account next).", "input_schema": {"connection_id": "int"}, "handler": _handle_supermarket_activate_connection},
    {"action": "supermarket.delete_connection", "description": "Delete a saved supermarket connection.", "input_schema": {"connection_id": "int"}, "handler": _handle_supermarket_delete_connection},
    {"action": "supermarket.list_offering_contexts", "description": "List the Auchan stores selectable for an address. Each entry carries `seller_id`, `store_reference`, `channel`, `name`, `address` and `distance` — feed them to `supermarket.select_auchan_store`.", "input_schema": {"zipcode": "string", "city": "string", "latitude": "float", "longitude": "float", "country": "string?"}, "handler": _handle_supermarket_list_offering_contexts},
    {"action": "supermarket.select_auchan_store", "description": "Select the Auchan store used for search (POST /journey/update + persist). Auchan prices are only server-rendered once a store is selected; searching without one returns a 400 'sélectionnez un magasin'.", "input_schema": {"seller_id": "string", "store_reference": "string", "store_label": "string", "channel": "string?", "location_label": "string?", "zipcode": "string?", "city": "string?", "country": "string?", "latitude": "float?", "longitude": "float?"}, "handler": _handle_supermarket_select_auchan_store},
    {"action": "supermarket.search", "description": "Search a supermarket and cache the normalized results. `store` accepts 'intermarche' (JSON API), 'carrefour' (JSON endpoint), 'leclerc' (JSON API + cookies) or 'auchan' (server-rendered HTML; works without login but requires a selected store via `supermarket.select_auchan_store`).", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan?", "queries": "string[]", "max_results": "int?", "promotions_only": "bool?"}, "handler": _handle_supermarket_search},
    {"action": "grocery.add_item", "description": "Add an item to grocery list", "input_schema": {"name": "string", "quantity": "float?", "unit": "string?", "category": "string?", "image_url": "string?", "store_label": "string?", "external_id": "string?", "packaging": "string?", "price_text": "string?", "product_url": "string?", "priority": "int?", "note": "string?"}, "handler": _handle_grocery_add_item},
    {"action": "grocery.list_items", "description": "List grocery items", "input_schema": {"checked": "bool?", "limit": "int?"}, "handler": _handle_grocery_list_items},
    {"action": "grocery.update_item", "description": "Update a grocery item", "input_schema": {"item_id": "int", "quantity": "float?", "unit": "string?", "category": "string?", "checked": "bool?", "priority": "int?", "note": "string?"}, "handler": _handle_grocery_update_item},
    {"action": "grocery.check_item", "description": "Mark grocery item checked or unchecked", "input_schema": {"item_id": "int", "checked": "bool?"}, "handler": _handle_grocery_check_item},
    {"action": "grocery.delete_item", "description": "Delete a grocery item", "input_schema": {"item_id": "int"}, "handler": _handle_grocery_delete_item},
    {"action": "video.fetch", "description": "Fetch transcript and description from a YouTube, Instagram, or TikTok URL", "input_schema": {"url": "string"}, "handler": _handle_video_fetch},
    {"action": "recipe.add", "description": "Create a recipe with optional ingredients", "input_schema": {"name": "string", "description": "string?", "instructions": "string", "steps": "string[]?", "utensils": "string[]?", "prep_minutes": "int?", "cook_minutes": "int?", "servings": "int?", "tags": "string[]?", "source_url": "string?", "source_platform": "string?", "source_title": "string?", "source_description": "string?", "source_transcript": "string?", "ingredients": "[{name, quantity, unit, note, category, cache_id}]?"}, "handler": _handle_recipe_add},
    {"action": "recipe.list", "description": "List recipes", "input_schema": {"limit": "int?"}, "handler": _handle_recipe_list},
    {"action": "recipe.get", "description": "Get one recipe by id", "input_schema": {"recipe_id": "int"}, "handler": _handle_recipe_get},
    {"action": "recipe.update", "description": "Update a recipe", "input_schema": {"recipe_id": "int", "name": "string?", "description": "string?", "instructions": "string?", "steps": "string[]?", "utensils": "string[]?", "prep_minutes": "int?", "cook_minutes": "int?", "servings": "int?", "tags": "string[]?", "source_url": "string?", "source_platform": "string?", "source_title": "string?", "source_description": "string?", "source_transcript": "string?", "ingredients": "[{name, quantity, unit, note, category, cache_id}]?"}, "handler": _handle_recipe_update},
    {"action": "recipe.confirm_cooked", "description": "Confirm a recipe was cooked and consume pantry ingredients (idempotent; undo with recipe.unconfirm_cooked)", "input_schema": {"recipe_id": "int", "servings_override": "int?", "note": "string?"}, "handler": _handle_recipe_confirm_cooked},
    {"action": "recipe.unconfirm_cooked", "description": "Undo a recipe-level cooked confirmation and restore pantry stock", "input_schema": {"recipe_id": "int"}, "handler": _handle_recipe_unconfirm_cooked},
    {"action": "recipe.delete", "description": "Delete a recipe and its dependent recipe ingredients / meal plans", "input_schema": {"recipe_id": "int"}, "handler": _handle_recipe_delete},
    {"action": "meal_plan.add", "description": "Plan a recipe at a specific datetime", "input_schema": {"planned_at": "datetime?", "planned_for": "YYYY-MM-DD? (legacy)", "slot": "breakfast|lunch|dinner? (legacy)", "recipe_id": "int", "servings_override": "int?", "note": "string?", "auto_add_missing_ingredients": "bool?"}, "handler": _handle_meal_plan_add},
    {"action": "meal_plan.log_cooked", "description": "Log a recipe as cooked without pre-planning", "input_schema": {"recipe_id": "int", "cooked_at": "datetime?", "servings_override": "int?", "note": "string?"}, "handler": _handle_meal_plan_log_cooked},
    {"action": "meal_plan.list", "description": "List meal plans", "input_schema": {"date_from": "YYYY-MM-DD?", "date_to": "YYYY-MM-DD?", "slot": "breakfast|lunch|dinner? (legacy)", "limit": "int?"}, "handler": _handle_meal_plan_list},
    {"action": "meal_plan.update", "description": "Update one meal plan", "input_schema": {"meal_plan_id": "int", "planned_at": "datetime?", "planned_for": "YYYY-MM-DD? (legacy)", "slot": "breakfast|lunch|dinner? (legacy)", "recipe_id": "int?", "servings_override": "int?", "note": "string?", "auto_add_missing_ingredients": "bool?"}, "handler": _handle_meal_plan_update},
    {"action": "meal_plan.delete", "description": "Delete one meal plan", "input_schema": {"meal_plan_id": "int"}, "handler": _handle_meal_plan_delete},
    {"action": "meal_plan.sync_groceries", "description": "Sync missing ingredients to grocery list for one meal plan", "input_schema": {"meal_plan_id": "int"}, "handler": _handle_meal_plan_sync_groceries},
    {"action": "meal_plan.confirm_cooked", "description": "Confirm meal was cooked and consume pantry ingredients", "input_schema": {"meal_plan_id": "int", "note": "string?"}, "handler": _handle_meal_plan_confirm_cooked},
    {"action": "meal_plan.unconfirm_cooked", "description": "Undo cooked confirmation and restore pantry", "input_schema": {"meal_plan_id": "int"}, "handler": _handle_meal_plan_unconfirm_cooked},
    {"action": "calendar.add_item", "description": "Create a manual calendar block only when the user wants a generic time slot and not a real task, habit, event, meal, subscription, or fitness session.", "input_schema": {"title": "string", "description": "string?", "start_at": "datetime", "end_at": "datetime", "all_day": "bool?", "category": "general|task|event|subscription|meal?", "notification_enabled": "bool?", "reminder_offsets_min": "int[]?", "metadata": "object?"}, "handler": _handle_calendar_add_item},
    {"action": "calendar.list_items", "description": "List calendar items", "input_schema": {"from_at": "datetime?", "to_at": "datetime?", "category": "general|task|event|subscription|meal?", "source": "manual|task|habit|event|subscription|meal_plan|fitness_session?", "include_completed": "bool?", "generated_only": "bool?", "limit": "int?"}, "handler": _handle_calendar_list_items},
    {"action": "calendar.update_item", "description": "Update calendar item", "input_schema": {"item_id": "int", "title": "string?", "description": "string?", "start_at": "datetime?", "end_at": "datetime?", "all_day": "bool?", "category": "general|task|event|subscription|meal?", "completed": "bool?", "notification_enabled": "bool?", "reminder_offsets_min": "int[]?", "metadata": "object?"}, "handler": _handle_calendar_update_item},
    {"action": "calendar.delete_item", "description": "Delete calendar item", "input_schema": {"item_id": "int"}, "handler": _handle_calendar_delete_item},
    {"action": "calendar.agenda", "description": "List day agenda", "input_schema": {"day": "YYYY-MM-DD?", "include_completed": "bool?"}, "handler": _handle_calendar_agenda},
    {"action": "calendar.sync", "description": "Sync tasks/events/subscriptions/meal plans into calendar", "input_schema": {}, "handler": _handle_calendar_sync},
    {"action": "calendar.due_reminders", "description": "List due reminders in next N minutes", "input_schema": {"within_minutes": "int?"}, "handler": _handle_calendar_due_reminders},
    {"action": "calendar.ack_reminder", "description": "Acknowledge reminders for a calendar item", "input_schema": {"item_id": "int"}, "handler": _handle_calendar_ack_reminder},
    {"action": "habit.create", "description": "Create a habit", "input_schema": {"name": "string", "description": "string?", "frequency": "daily|weekly?", "target_per_period": "int?", "schedule_time": "HH:MM?", "schedule_times": "HH:MM[]?", "schedule_weekday": "0=Monday..6=Sunday?", "schedule_weekdays": "0..6[]?", "duration_minutes": "int?"}, "handler": _handle_habit_create},
    {"action": "habit.list", "description": "List habits", "input_schema": {"active_only": "bool?"}, "handler": _handle_habit_list},
    {"action": "habit.update", "description": "Update a habit", "input_schema": {"habit_id": "int", "name": "string?", "description": "string?", "frequency": "daily|weekly?", "target_per_period": "int?", "schedule_time": "HH:MM?", "schedule_times": "HH:MM[]?", "schedule_weekday": "0=Monday..6=Sunday?", "schedule_weekdays": "0..6[]?", "duration_minutes": "int?", "active": "bool?"}, "handler": _handle_habit_update},
    {"action": "habit.set_active", "description": "Activate or deactivate a habit", "input_schema": {"habit_id": "int", "active": "bool"}, "handler": _handle_habit_set_active},
    {"action": "habit.log", "description": "Log completion for a habit", "input_schema": {"habit_id": "int", "value": "int?", "note": "string?"}, "handler": _handle_habit_log},
    {"action": "habit.list_logs", "description": "List logs for one habit", "input_schema": {"habit_id": "int", "limit": "int?"}, "handler": _handle_habit_list_logs},
    {"action": "goal.create", "description": "Create a goal", "input_schema": {"title": "string", "description": "string?", "status": "planned|active|completed|paused|cancelled?", "progress_percent": "int?", "target_date": "YYYY-MM-DD?", "tags": "string[]?"}, "handler": _handle_goal_create},
    {"action": "goal.list", "description": "List goals", "input_schema": {"status": "planned|active|completed|paused|cancelled?", "limit": "int?"}, "handler": _handle_goal_list},
    {"action": "goal.get", "description": "Get one goal", "input_schema": {"goal_id": "int"}, "handler": _handle_goal_get},
    {"action": "goal.update", "description": "Update a goal", "input_schema": {"goal_id": "int", "title": "string?", "description": "string?", "status": "planned|active|completed|paused|cancelled?", "progress_percent": "int?", "target_date": "YYYY-MM-DD?", "tags": "string[]?"}, "handler": _handle_goal_update},
    {"action": "goal.add_milestone", "description": "Add a milestone to a goal", "input_schema": {"goal_id": "int", "title": "string", "due_at": "datetime?"}, "handler": _handle_goal_add_milestone},
    {"action": "goal.list_milestones", "description": "List milestones for a goal", "input_schema": {"goal_id": "int", "limit": "int?"}, "handler": _handle_goal_list_milestones},
    {"action": "goal.update_milestone", "description": "Update a goal milestone", "input_schema": {"goal_id": "int", "milestone_id": "int", "title": "string?", "due_at": "datetime?", "completed": "bool?"}, "handler": _handle_goal_update_milestone},
    {"action": "event.create", "description": "Create calendar event", "input_schema": {"title": "string", "description": "string?", "start_at": "datetime", "end_at": "datetime", "location": "string?", "type": "personal|work|health|finance|social?", "all_day": "bool?", "tags": "string[]?"}, "handler": _handle_event_create},
    {"action": "event.list", "description": "List events", "input_schema": {"from_at": "datetime?", "to_at": "datetime?", "type": "personal|work|health|finance|social?", "limit": "int?"}, "handler": _handle_event_list},
    {"action": "event.upcoming", "description": "List upcoming events", "input_schema": {"days": "int?", "type": "personal|work|health|finance|social?"}, "handler": _handle_event_upcoming},
    {"action": "event.get", "description": "Get one event", "input_schema": {"event_id": "int"}, "handler": _handle_event_get},
    {"action": "event.update", "description": "Update an event", "input_schema": {"event_id": "int", "title": "string?", "description": "string?", "start_at": "datetime?", "end_at": "datetime?", "location": "string?", "type": "personal|work|health|finance|social?", "all_day": "bool?", "tags": "string[]?"}, "handler": _handle_event_update},
    {"action": "event.delete", "description": "Delete an event", "input_schema": {"event_id": "int"}, "handler": _handle_event_delete},
    {"action": "subscription.create", "description": "Create subscription", "input_schema": {"name": "string", "category": "string?", "amount": "float", "currency": "string?", "interval": "weekly|monthly|yearly?", "next_due_date": "YYYY-MM-DD", "autopay": "bool?", "active": "bool?", "note": "string?"}, "handler": _handle_subscription_create},
    {"action": "subscription.list", "description": "List subscriptions", "input_schema": {"active_only": "bool?", "limit": "int?"}, "handler": _handle_subscription_list},
    {"action": "subscription.get", "description": "Get one subscription", "input_schema": {"subscription_id": "int"}, "handler": _handle_subscription_get},
    {"action": "subscription.update", "description": "Update subscription", "input_schema": {"subscription_id": "int", "name": "string?", "category": "string?", "amount": "float?", "currency": "string?", "interval": "weekly|monthly|yearly?", "next_due_date": "YYYY-MM-DD?", "autopay": "bool?", "active": "bool?", "note": "string?"}, "handler": _handle_subscription_update},
    {"action": "subscription.upcoming", "description": "List upcoming subscriptions", "input_schema": {"days": "int?"}, "handler": _handle_subscription_upcoming},
    {"action": "subscription.projection", "description": "Compute monthly and yearly subscription projection", "input_schema": {"currency": "string?"}, "handler": _handle_subscription_projection},
    {"action": "patrimony.overview", "description": "Return patrimony overview with net worth, accounts, and savings goals", "input_schema": {}, "handler": _handle_patrimony_overview},
    {"action": "patrimony.list_accounts", "description": "List patrimony accounts", "input_schema": {"active_only": "bool?"}, "handler": _handle_patrimony_list_accounts},
    {"action": "patrimony.add_account", "description": "Create a patrimony account", "input_schema": {"name": "string", "account_type": "checking|savings|investment|crypto|other?", "balance": "float?", "currency": "string?", "institution": "string?", "note": "string?"}, "handler": _handle_patrimony_add_account},
    {"action": "patrimony.update_account", "description": "Update a patrimony account", "input_schema": {"account_id": "int", "name": "string?", "account_type": "checking|savings|investment|crypto|other?", "balance": "float?", "currency": "string?", "institution": "string?", "note": "string?", "is_active": "bool?"}, "handler": _handle_patrimony_update_account},
    {"action": "patrimony.delete_account", "description": "Delete a patrimony account", "input_schema": {"account_id": "int"}, "handler": _handle_patrimony_delete_account},
    {"action": "patrimony.list_goals", "description": "List savings goals", "input_schema": {}, "handler": _handle_patrimony_list_goals},
    {"action": "patrimony.add_goal", "description": "Create a savings goal", "input_schema": {"title": "string", "target_amount": "float", "current_amount": "float?", "currency": "string?", "target_date": "YYYY-MM-DD?", "account_id": "int?", "note": "string?"}, "handler": _handle_patrimony_add_goal},
    {"action": "patrimony.update_goal", "description": "Update a savings goal", "input_schema": {"goal_id": "int", "title": "string?", "target_amount": "float?", "current_amount": "float?", "currency": "string?", "target_date": "YYYY-MM-DD?", "account_id": "int?", "note": "string?", "completed": "bool?"}, "handler": _handle_patrimony_update_goal},
    {"action": "patrimony.delete_goal", "description": "Delete a savings goal", "input_schema": {"goal_id": "int"}, "handler": _handle_patrimony_delete_goal},
    {"action": "pantry.add_item", "description": "Add pantry item", "input_schema": {"name": "string", "quantity": "float?", "unit": "string?", "category": "string?", "min_quantity": "float?", "expires_at": "YYYY-MM-DD?", "location": "string?", "note": "string?"}, "handler": _handle_pantry_add_item},
    {"action": "pantry.list_items", "description": "List pantry items", "input_schema": {"low_stock_only": "bool?", "expiring_in_days": "int?", "limit": "int?"}, "handler": _handle_pantry_list_items},
    {"action": "pantry.update_item", "description": "Update pantry item", "input_schema": {"item_id": "int", "quantity": "float?", "unit": "string?", "category": "string?", "min_quantity": "float?", "expires_at": "YYYY-MM-DD?", "location": "string?", "note": "string?"}, "handler": _handle_pantry_update_item},
    {"action": "pantry.consume_item", "description": "Decrease pantry item quantity", "input_schema": {"item_id": "int", "amount": "float"}, "handler": _handle_pantry_consume_item},
    {"action": "pantry.delete_item", "description": "Delete pantry item", "input_schema": {"item_id": "int"}, "handler": _handle_pantry_delete_item},
    {"action": "pantry.overview", "description": "Get pantry overview", "input_schema": {"days": "int?"}, "handler": _handle_pantry_overview},
    {"action": "note.create", "description": "Create note", "input_schema": {"title": "string", "content": "string", "kind": "note|journal|idea?", "tags": "string[]?", "pinned": "bool?", "mood": "1..10?"}, "handler": _handle_note_create},
    {"action": "note.list", "description": "List notes", "input_schema": {"kind": "note|journal|idea?", "tag": "string?", "q": "string?", "pinned": "bool?", "limit": "int?"}, "handler": _handle_note_list},
    {"action": "note.get", "description": "Get one note", "input_schema": {"note_id": "int"}, "handler": _handle_note_get},
    {"action": "note.update", "description": "Update note", "input_schema": {"note_id": "int", "title": "string?", "content": "string?", "kind": "note|journal|idea?", "tags": "string[]?", "pinned": "bool?", "mood": "1..10?"}, "handler": _handle_note_update},
    {"action": "note.delete", "description": "Delete note", "input_schema": {"note_id": "int"}, "handler": _handle_note_delete},
    {"action": "note.journal", "description": "List journal entries", "input_schema": {"from_date": "YYYY-MM-DD?", "to_date": "YYYY-MM-DD?", "limit": "int?"}, "handler": _handle_note_journal},
    {"action": "dashboard.overview", "description": "Return current productivity and life overview", "input_schema": {}, "handler": _handle_dashboard_overview},
]


def _action_registry() -> dict[str, dict]:
    """Action name -> catalog entry (the catalog IS the dispatch)."""
    return {entry["action"]: entry for entry in ACTION_CATALOG}


_ACTION_REGISTRY = _action_registry()


def action_catalog_manifest() -> list[dict]:
    """ACTION_CATALOG without the dispatch-only `handler` key, for the manifest."""
    return [
        {key: value for key, value in entry.items() if key != "handler"}
        for entry in ACTION_CATALOG
    ]


def execute_action(
    action: str,
    payload: dict,
    session,
    *,
    user: User | None = None,
) -> dict:
    entry = _ACTION_REGISTRY.get(action)
    if entry is None:
        raise ValueError(f"Unknown action: {action}")
    now = datetime.now(timezone.utc)
    user_id = user.id if user is not None else None
    return entry["handler"](payload, session, user=user, now=now, user_id=user_id)
