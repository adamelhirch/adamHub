import asyncio
from datetime import date, datetime, time, timedelta, timezone

from sqlmodel import select

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
    HabitLog,
    LinearIssueCache,
    LinearProjectCache,
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
    SupermarketStore,
    Task,
    TaskStatus,
    TransactionKind,
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
    LinearIssueCreate,
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
from app.services.linear_hub import (
    LinearIntegrationError,
    create_issue as create_linear_issue_live,
    fetch_issues as fetch_linear_issues_live,
    fetch_projects as fetch_linear_projects_live,
    sync_linear_cache,
)
from app.services.meal_planning import (
    build_meal_plan_read,
    compute_recipe_missing_ingredients,
    consume_recipe_ingredients,
    confirm_meal_plan_cooked,
    sync_meal_plan_to_grocery,
    unconfirm_meal_plan_cooked,
)
from app.services.calendar_hub import (
    build_calendar_item_read,
    list_due_reminders,
    sync_generated_calendar_items,
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
from app.services.scraper_service import fetch_search_results, upsert_search_cache
from app.services.supermarket_registry import list_store_definitions
from app.services.video_intake import extract_video_source

ACTION_CATALOG = [
    {"action": "task.create", "description": "Create a one-shot task. For a scheduled task, use due_at plus estimated_minutes. If the user wants a checklist or steps, store them in subtasks. Do not use calendar.add_item for normal tasks.", "input_schema": {"title": "string", "description": "string?", "subtasks": "[{id?, title, completed}]?", "schedule_mode": "none|once|daily|weekly?", "schedule_time": "HH:MM?", "schedule_weekday": "0=Monday..6=Sunday?", "due_at": "datetime?", "priority": "low|medium|high|urgent", "estimated_minutes": "int?", "tags": "string[]?"}},
    {"action": "task.list", "description": "List tasks with optional status filter", "input_schema": {"status": "todo|in_progress|done|blocked?", "only_open": "bool?", "limit": "int?"}},
    {"action": "task.update", "description": "Update an existing task. Use this to change title, description, checklist, timing, duration, or status. Keep task scheduling inside task.update, not calendar.update_item.", "input_schema": {"task_id": "int", "title": "string?", "description": "string?", "subtasks": "[{id?, title, completed}]?", "schedule_mode": "none|once|daily|weekly?", "schedule_time": "HH:MM?", "schedule_weekday": "0=Monday..6=Sunday?", "due_at": "datetime?", "priority": "low|medium|high|urgent?", "status": "todo|in_progress|done|blocked?", "estimated_minutes": "int?", "tags": "string[]?"}},
    {"action": "task.complete", "description": "Mark a task as done", "input_schema": {"task_id": "int"}},
    {"action": "finance.add_transaction", "description": "Add an income or expense transaction", "input_schema": {"kind": "income|expense", "amount": "float", "currency": "string?", "category": "string", "note": "string?", "occurred_at": "datetime?", "is_recurring": "bool?"}},
    {"action": "finance.list_transactions", "description": "List transactions", "input_schema": {"kind": "income|expense?", "year": "int?", "month": "int?", "limit": "int?"}},
    {"action": "finance.create_budget", "description": "Create a monthly category budget", "input_schema": {"month": "YYYY-MM", "category": "string", "monthly_limit": "float", "currency": "string?", "alert_threshold": "float?"}},
    {"action": "finance.list_budgets", "description": "List budgets with optional month", "input_schema": {"month": "YYYY-MM?"}},
    {"action": "finance.month_summary", "description": "Compute month financial summary", "input_schema": {"year": "int?", "month": "int?"}},
    {"action": "fitness.overview", "description": "Return the fitness dashboard overview", "input_schema": {}},
    {"action": "fitness.list_sessions", "description": "List fitness sessions", "input_schema": {"limit": "int?"}},
    {"action": "fitness.create_session", "description": "Create a fitness session", "input_schema": {"title": "string", "session_type": "strength|cardio|mobility|recovery|mixed?", "planned_at": "datetime?", "duration_minutes": "int?", "exercises": "[{name, mode, reps, duration_minutes, note}|string]?", "note": "string?"}},
    {"action": "fitness.update_session", "description": "Update a fitness session", "input_schema": {"session_id": "int", "title": "string?", "session_type": "strength|cardio|mobility|recovery|mixed?", "planned_at": "datetime?", "duration_minutes": "int?", "exercises": "[{name, mode, reps, duration_minutes, note}|string]?", "note": "string?", "status": "planned|completed|skipped?", "actual_duration_minutes": "int?", "effort_rating": "int?", "calories_burned": "float?"}},
    {"action": "fitness.complete_session", "description": "Mark a fitness session as completed", "input_schema": {"session_id": "int", "note": "string?", "actual_duration_minutes": "int?", "effort_rating": "int?", "calories_burned": "float?"}},
    {"action": "fitness.delete_session", "description": "Delete a fitness session", "input_schema": {"session_id": "int"}},
    {"action": "fitness.list_measurements", "description": "List fitness measurements", "input_schema": {"limit": "int?"}},
    {"action": "fitness.add_measurement", "description": "Add a fitness measurement", "input_schema": {"recorded_at": "datetime?", "body_weight_kg": "float?", "body_fat_pct": "float?", "resting_hr": "int?", "sleep_hours": "float?", "steps": "int?", "note": "string?"}},
    {"action": "fitness.update_measurement", "description": "Update a fitness measurement", "input_schema": {"measurement_id": "int", "recorded_at": "datetime?", "body_weight_kg": "float?", "body_fat_pct": "float?", "resting_hr": "int?", "sleep_hours": "float?", "steps": "int?", "note": "string?"}},
    {"action": "fitness.delete_measurement", "description": "Delete a fitness measurement", "input_schema": {"measurement_id": "int"}},
    {"action": "supermarket.list_stores", "description": "List supported supermarket stores and capabilities", "input_schema": {}},
    {"action": "supermarket.search", "description": "Search a supermarket and cache the normalized results", "input_schema": {"store": "intermarche?", "queries": "string[]", "max_results": "int?", "promotions_only": "bool?"}},
    {"action": "grocery.add_item", "description": "Add an item to grocery list", "input_schema": {"name": "string", "quantity": "float?", "unit": "string?", "category": "string?", "image_url": "string?", "store_label": "string?", "external_id": "string?", "packaging": "string?", "price_text": "string?", "product_url": "string?", "priority": "int?", "note": "string?"}},
    {"action": "grocery.list_items", "description": "List grocery items", "input_schema": {"checked": "bool?", "limit": "int?"}},
    {"action": "grocery.update_item", "description": "Update a grocery item", "input_schema": {"item_id": "int", "quantity": "float?", "unit": "string?", "category": "string?", "checked": "bool?", "priority": "int?", "note": "string?"}},
    {"action": "grocery.check_item", "description": "Mark grocery item checked or unchecked", "input_schema": {"item_id": "int", "checked": "bool?"}},
    {"action": "grocery.delete_item", "description": "Delete a grocery item", "input_schema": {"item_id": "int"}},
    {"action": "video.fetch", "description": "Fetch transcript and description from a YouTube, Instagram, or TikTok URL", "input_schema": {"url": "string"}},
    {"action": "recipe.add", "description": "Create a recipe with optional ingredients", "input_schema": {"name": "string", "description": "string?", "instructions": "string", "steps": "string[]?", "utensils": "string[]?", "prep_minutes": "int?", "cook_minutes": "int?", "servings": "int?", "tags": "string[]?", "source_url": "string?", "source_platform": "string?", "source_title": "string?", "source_description": "string?", "source_transcript": "string?", "ingredients": "[{name, quantity, unit, note, store, store_label, external_id, category, packaging, price_text, product_url, image_url}]?"}},
    {"action": "recipe.list", "description": "List recipes", "input_schema": {"limit": "int?"}},
    {"action": "recipe.get", "description": "Get one recipe by id", "input_schema": {"recipe_id": "int"}},
    {"action": "recipe.update", "description": "Update a recipe", "input_schema": {"recipe_id": "int", "name": "string?", "description": "string?", "instructions": "string?", "steps": "string[]?", "utensils": "string[]?", "prep_minutes": "int?", "cook_minutes": "int?", "servings": "int?", "tags": "string[]?", "source_url": "string?", "source_platform": "string?", "source_title": "string?", "source_description": "string?", "source_transcript": "string?", "ingredients": "[{name, quantity, unit, note, store, store_label, external_id, category, packaging, price_text, product_url, image_url}]?"}},
    {"action": "recipe.confirm_cooked", "description": "Confirm a recipe was cooked and consume pantry ingredients", "input_schema": {"recipe_id": "int", "servings_override": "int?", "note": "string?"}},
    {"action": "recipe.delete", "description": "Delete a recipe and its dependent recipe ingredients / meal plans", "input_schema": {"recipe_id": "int"}},
    {"action": "meal_plan.add", "description": "Plan a recipe at a specific datetime", "input_schema": {"planned_at": "datetime?", "planned_for": "YYYY-MM-DD? (legacy)", "slot": "breakfast|lunch|dinner? (legacy)", "recipe_id": "int", "servings_override": "int?", "note": "string?", "auto_add_missing_ingredients": "bool?"}},
    {"action": "meal_plan.log_cooked", "description": "Log a recipe as cooked without pre-planning", "input_schema": {"recipe_id": "int", "cooked_at": "datetime?", "servings_override": "int?", "note": "string?"}},
    {"action": "meal_plan.list", "description": "List meal plans", "input_schema": {"date_from": "YYYY-MM-DD?", "date_to": "YYYY-MM-DD?", "slot": "breakfast|lunch|dinner? (legacy)", "limit": "int?"}},
    {"action": "meal_plan.update", "description": "Update one meal plan", "input_schema": {"meal_plan_id": "int", "planned_at": "datetime?", "planned_for": "YYYY-MM-DD? (legacy)", "slot": "breakfast|lunch|dinner? (legacy)", "recipe_id": "int?", "servings_override": "int?", "note": "string?", "auto_add_missing_ingredients": "bool?"}},
    {"action": "meal_plan.delete", "description": "Delete one meal plan", "input_schema": {"meal_plan_id": "int"}},
    {"action": "meal_plan.sync_groceries", "description": "Sync missing ingredients to grocery list for one meal plan", "input_schema": {"meal_plan_id": "int"}},
    {"action": "meal_plan.confirm_cooked", "description": "Confirm meal was cooked and consume pantry ingredients", "input_schema": {"meal_plan_id": "int", "note": "string?"}},
    {"action": "meal_plan.unconfirm_cooked", "description": "Undo cooked confirmation and restore pantry", "input_schema": {"meal_plan_id": "int"}},
    {"action": "calendar.add_item", "description": "Create a manual calendar block only when the user wants a generic time slot and not a real task, habit, event, meal, subscription, or fitness session.", "input_schema": {"title": "string", "description": "string?", "start_at": "datetime", "end_at": "datetime", "all_day": "bool?", "category": "general|task|event|subscription|meal?", "notification_enabled": "bool?", "reminder_offsets_min": "int[]?", "metadata": "object?"}},
    {"action": "calendar.list_items", "description": "List calendar items", "input_schema": {"from_at": "datetime?", "to_at": "datetime?", "category": "general|task|event|subscription|meal?", "source": "manual|task|habit|event|subscription|meal_plan|fitness_session?", "include_completed": "bool?", "generated_only": "bool?", "limit": "int?"}},
    {"action": "calendar.update_item", "description": "Update calendar item", "input_schema": {"item_id": "int", "title": "string?", "description": "string?", "start_at": "datetime?", "end_at": "datetime?", "all_day": "bool?", "category": "general|task|event|subscription|meal?", "completed": "bool?", "notification_enabled": "bool?", "reminder_offsets_min": "int[]?", "metadata": "object?"}},
    {"action": "calendar.delete_item", "description": "Delete calendar item", "input_schema": {"item_id": "int"}},
    {"action": "calendar.agenda", "description": "List day agenda", "input_schema": {"day": "YYYY-MM-DD?", "include_completed": "bool?"}},
    {"action": "calendar.sync", "description": "Sync tasks/events/subscriptions/meal plans into calendar", "input_schema": {}},
    {"action": "calendar.due_reminders", "description": "List due reminders in next N minutes", "input_schema": {"within_minutes": "int?"}},
    {"action": "calendar.ack_reminder", "description": "Acknowledge reminders for a calendar item", "input_schema": {"item_id": "int"}},
    {"action": "habit.create", "description": "Create a habit", "input_schema": {"name": "string", "description": "string?", "frequency": "daily|weekly?", "target_per_period": "int?", "schedule_time": "HH:MM?", "schedule_times": "HH:MM[]?", "schedule_weekday": "0=Monday..6=Sunday?", "schedule_weekdays": "0..6[]?", "duration_minutes": "int?"}},
    {"action": "habit.list", "description": "List habits", "input_schema": {"active_only": "bool?"}},
    {"action": "habit.set_active", "description": "Activate or deactivate a habit", "input_schema": {"habit_id": "int", "active": "bool"}},
    {"action": "habit.log", "description": "Log completion for a habit", "input_schema": {"habit_id": "int", "value": "int?", "note": "string?"}},
    {"action": "habit.list_logs", "description": "List logs for one habit", "input_schema": {"habit_id": "int", "limit": "int?"}},
    {"action": "goal.create", "description": "Create a goal", "input_schema": {"title": "string", "description": "string?", "status": "planned|active|completed|paused|cancelled?", "progress_percent": "int?", "target_date": "YYYY-MM-DD?", "tags": "string[]?"}},
    {"action": "goal.list", "description": "List goals", "input_schema": {"status": "planned|active|completed|paused|cancelled?", "limit": "int?"}},
    {"action": "goal.get", "description": "Get one goal", "input_schema": {"goal_id": "int"}},
    {"action": "goal.update", "description": "Update a goal", "input_schema": {"goal_id": "int", "title": "string?", "description": "string?", "status": "planned|active|completed|paused|cancelled?", "progress_percent": "int?", "target_date": "YYYY-MM-DD?", "tags": "string[]?"}},
    {"action": "goal.add_milestone", "description": "Add a milestone to a goal", "input_schema": {"goal_id": "int", "title": "string", "due_at": "datetime?"}},
    {"action": "goal.list_milestones", "description": "List milestones for a goal", "input_schema": {"goal_id": "int", "limit": "int?"}},
    {"action": "goal.update_milestone", "description": "Update a goal milestone", "input_schema": {"goal_id": "int", "milestone_id": "int", "title": "string?", "due_at": "datetime?", "completed": "bool?"}},
    {"action": "event.create", "description": "Create calendar event", "input_schema": {"title": "string", "description": "string?", "start_at": "datetime", "end_at": "datetime", "location": "string?", "type": "personal|work|health|finance|social?", "all_day": "bool?", "tags": "string[]?"}},
    {"action": "event.list", "description": "List events", "input_schema": {"from_at": "datetime?", "to_at": "datetime?", "type": "personal|work|health|finance|social?", "limit": "int?"}},
    {"action": "event.upcoming", "description": "List upcoming events", "input_schema": {"days": "int?", "type": "personal|work|health|finance|social?"}},
    {"action": "event.get", "description": "Get one event", "input_schema": {"event_id": "int"}},
    {"action": "event.update", "description": "Update an event", "input_schema": {"event_id": "int", "title": "string?", "description": "string?", "start_at": "datetime?", "end_at": "datetime?", "location": "string?", "type": "personal|work|health|finance|social?", "all_day": "bool?", "tags": "string[]?"}},
    {"action": "event.delete", "description": "Delete an event", "input_schema": {"event_id": "int"}},
    {"action": "subscription.create", "description": "Create subscription", "input_schema": {"name": "string", "category": "string?", "amount": "float", "currency": "string?", "interval": "weekly|monthly|yearly?", "next_due_date": "YYYY-MM-DD", "autopay": "bool?", "active": "bool?", "note": "string?"}},
    {"action": "subscription.list", "description": "List subscriptions", "input_schema": {"active_only": "bool?", "limit": "int?"}},
    {"action": "subscription.get", "description": "Get one subscription", "input_schema": {"subscription_id": "int"}},
    {"action": "subscription.update", "description": "Update subscription", "input_schema": {"subscription_id": "int", "name": "string?", "category": "string?", "amount": "float?", "currency": "string?", "interval": "weekly|monthly|yearly?", "next_due_date": "YYYY-MM-DD?", "autopay": "bool?", "active": "bool?", "note": "string?"}},
    {"action": "subscription.upcoming", "description": "List upcoming subscriptions", "input_schema": {"days": "int?"}},
    {"action": "subscription.projection", "description": "Compute monthly and yearly subscription projection", "input_schema": {"currency": "string?"}},
    {"action": "patrimony.overview", "description": "Return patrimony overview with net worth, accounts, and savings goals", "input_schema": {}},
    {"action": "patrimony.list_accounts", "description": "List patrimony accounts", "input_schema": {"active_only": "bool?"}},
    {"action": "patrimony.add_account", "description": "Create a patrimony account", "input_schema": {"name": "string", "account_type": "checking|savings|investment|crypto|other?", "balance": "float?", "currency": "string?", "institution": "string?", "note": "string?"}},
    {"action": "patrimony.update_account", "description": "Update a patrimony account", "input_schema": {"account_id": "int", "name": "string?", "account_type": "checking|savings|investment|crypto|other?", "balance": "float?", "currency": "string?", "institution": "string?", "note": "string?", "is_active": "bool?"}},
    {"action": "patrimony.delete_account", "description": "Delete a patrimony account", "input_schema": {"account_id": "int"}},
    {"action": "patrimony.list_goals", "description": "List savings goals", "input_schema": {}},
    {"action": "patrimony.add_goal", "description": "Create a savings goal", "input_schema": {"title": "string", "target_amount": "float", "current_amount": "float?", "currency": "string?", "target_date": "YYYY-MM-DD?", "account_id": "int?", "note": "string?"}},
    {"action": "patrimony.update_goal", "description": "Update a savings goal", "input_schema": {"goal_id": "int", "title": "string?", "target_amount": "float?", "current_amount": "float?", "currency": "string?", "target_date": "YYYY-MM-DD?", "account_id": "int?", "note": "string?", "completed": "bool?"}},
    {"action": "patrimony.delete_goal", "description": "Delete a savings goal", "input_schema": {"goal_id": "int"}},
    {"action": "pantry.add_item", "description": "Add pantry item", "input_schema": {"name": "string", "quantity": "float?", "unit": "string?", "category": "string?", "min_quantity": "float?", "expires_at": "YYYY-MM-DD?", "location": "string?", "note": "string?"}},
    {"action": "pantry.list_items", "description": "List pantry items", "input_schema": {"low_stock_only": "bool?", "expiring_in_days": "int?", "limit": "int?"}},
    {"action": "pantry.update_item", "description": "Update pantry item", "input_schema": {"item_id": "int", "quantity": "float?", "unit": "string?", "category": "string?", "min_quantity": "float?", "expires_at": "YYYY-MM-DD?", "location": "string?", "note": "string?"}},
    {"action": "pantry.consume_item", "description": "Decrease pantry item quantity", "input_schema": {"item_id": "int", "amount": "float"}},
    {"action": "pantry.delete_item", "description": "Delete pantry item", "input_schema": {"item_id": "int"}},
    {"action": "pantry.overview", "description": "Get pantry overview", "input_schema": {"days": "int?"}},
    {"action": "note.create", "description": "Create note", "input_schema": {"title": "string", "content": "string", "kind": "note|journal|idea?", "tags": "string[]?", "pinned": "bool?", "mood": "1..10?"}},
    {"action": "note.list", "description": "List notes", "input_schema": {"kind": "note|journal|idea?", "tag": "string?", "q": "string?", "pinned": "bool?", "limit": "int?"}},
    {"action": "note.get", "description": "Get one note", "input_schema": {"note_id": "int"}},
    {"action": "note.update", "description": "Update note", "input_schema": {"note_id": "int", "title": "string?", "content": "string?", "kind": "note|journal|idea?", "tags": "string[]?", "pinned": "bool?", "mood": "1..10?"}},
    {"action": "note.delete", "description": "Delete note", "input_schema": {"note_id": "int"}},
    {"action": "note.journal", "description": "List journal entries", "input_schema": {"from_date": "YYYY-MM-DD?", "to_date": "YYYY-MM-DD?", "limit": "int?"}},
    {"action": "linear.projects", "description": "List Linear projects", "input_schema": {"source": "cache|live?", "limit": "int?"}},
    {"action": "linear.issues", "description": "List Linear issues", "input_schema": {"project_id": "string?", "source": "cache|live?", "limit": "int?"}},
    {"action": "linear.issue_create", "description": "Create a Linear issue", "input_schema": {"title": "string", "description": "string?", "project_id": "string?", "team_id": "string?", "priority": "0..4?", "assignee_id": "string?", "due_date": "YYYY-MM-DD?"}},
    {"action": "linear.sync", "description": "Sync Linear projects/issues into local cache", "input_schema": {"project_id": "string?"}},
    {"action": "dashboard.overview", "description": "Return current productivity and life overview", "input_schema": {}},
]


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


def execute_action(action: str, payload: dict, session) -> dict:
    now = datetime.now(timezone.utc)

    if action == "task.create":
        data = TaskCreate.model_validate(payload)
        task = Task(**data.model_dump())
        validate_task_schedule_free(session, task)
        session.add(task)
        session.commit()
        session.refresh(task)
        return {"task": task.model_dump(mode="json")}

    if action == "task.list":
        limit = _clamp_int(payload.get("limit"), default=25, minimum=1, maximum=100)
        only_open = _as_bool(payload.get("only_open"), default=False)
        statement = select(Task).order_by(Task.created_at.desc()).limit(limit)

        if payload.get("status"):
            statement = statement.where(Task.status == TaskStatus(payload["status"]))
        if only_open:
            statement = statement.where(Task.status != TaskStatus.DONE)

        tasks = session.exec(statement).all()
        return {"tasks": [task.model_dump(mode="json") for task in tasks]}

    if action == "task.update":
        task_id = int(payload.get("task_id", 0))
        task = session.get(Task, task_id)
        if not task:
            raise ValueError("task_id not found")

        patch = TaskUpdate.model_validate({k: v for k, v in payload.items() if k != "task_id"})
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No task fields to update")

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

        validate_task_schedule_free(session, task, ignore_task_id=task.id)
        task.updated_at = now

        session.add(task)
        session.commit()
        session.refresh(task)
        return {"task": task.model_dump(mode="json")}

    if action == "task.complete":
        task_id = int(payload.get("task_id", 0))
        task = session.get(Task, task_id)
        if not task:
            raise ValueError("task_id not found")
        task.status = TaskStatus.DONE
        task.updated_at = now
        session.add(task)
        session.commit()
        session.refresh(task)
        return {"task": task.model_dump(mode="json")}

    if action == "finance.add_transaction":
        data = FinanceTransactionCreate.model_validate(payload)
        tx = FinanceTransaction(**data.model_dump())
        if tx.occurred_at is None:
            tx.occurred_at = now
        session.add(tx)
        session.commit()
        session.refresh(tx)
        return {"transaction": tx.model_dump(mode="json")}

    if action == "finance.list_transactions":
        limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=300)
        statement = select(FinanceTransaction).order_by(FinanceTransaction.occurred_at.desc()).limit(limit)

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

    if action == "finance.create_budget":
        data = BudgetCreate.model_validate(payload)
        if len(data.month) != 7 or data.month[4] != "-":
            raise ValueError("month must be in format YYYY-MM")
        budget = Budget(**data.model_dump())
        session.add(budget)
        session.commit()
        session.refresh(budget)
        return {"budget": budget.model_dump(mode="json")}

    if action == "finance.list_budgets":
        statement = select(Budget).order_by(Budget.month.desc(), Budget.category.asc())
        if payload.get("month"):
            statement = statement.where(Budget.month == payload["month"])
        budgets = session.exec(statement).all()
        return {"budgets": [budget.model_dump(mode="json") for budget in budgets]}

    if action == "finance.month_summary":
        year = int(payload.get("year", now.year))
        month = int(payload.get("month", now.month))
        summary = build_month_summary(session, year, month)
        return {"summary": summary.model_dump(mode="json")}

    if action == "fitness.overview":
        return {"overview": build_fitness_overview(session).model_dump(mode="json")}

    if action == "fitness.list_sessions":
        limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=300)
        rows = session.exec(
            select(FitnessSession).order_by(FitnessSession.planned_at.desc()).limit(limit)
        ).all()
        return {"sessions": [build_fitness_session_read(row).model_dump(mode="json") for row in rows]}

    if action == "fitness.create_session":
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

    if action == "fitness.update_session":
        session_id = int(payload.get("session_id", 0))
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

    if action == "fitness.complete_session":
        session_id = int(payload.get("session_id", 0))
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

    if action == "fitness.delete_session":
        session_id = int(payload.get("session_id", 0))
        row = session.get(FitnessSession, session_id)
        if not row:
            raise ValueError("session_id not found")
        session.delete(row)
        session.commit()
        return {"ok": True, "deleted_id": session_id}

    if action == "fitness.list_measurements":
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

    if action == "fitness.add_measurement":
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
        session.add(row)
        session.commit()
        session.refresh(row)
        return {"measurement": build_fitness_measurement_read(row).model_dump(mode="json")}

    if action == "fitness.update_measurement":
        measurement_id = int(payload.get("measurement_id", 0))
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

        for key, value in updates.items():
            setattr(row, key, value)

        row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        return {"measurement": build_fitness_measurement_read(row).model_dump(mode="json")}

    if action == "fitness.delete_measurement":
        measurement_id = int(payload.get("measurement_id", 0))
        row = session.get(FitnessMeasurement, measurement_id)
        if not row:
            raise ValueError("measurement_id not found")
        session.delete(row)
        session.commit()
        return {"ok": True, "deleted_id": measurement_id}

    if action == "grocery.add_item":
        data = GroceryItemCreate.model_validate(payload)
        item = GroceryItem(**data.model_dump())
        session.add(item)
        session.commit()
        session.refresh(item)
        return {"item": item.model_dump(mode="json")}

    if action == "supermarket.list_stores":
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

    if action == "supermarket.search":
        store = payload.get("store") or "intermarche"
        queries = payload.get("queries")
        if isinstance(queries, str):
            queries = [queries]
        if not isinstance(queries, list) or not queries:
            raise ValueError("queries must be a non-empty list")
        max_results = _clamp_int(payload.get("max_results"), default=10, minimum=1, maximum=30)
        promotions_only = _as_bool(payload.get("promotions_only"), default=False)
        if store != "intermarche":
            raise ValueError("Unsupported supermarket store")
        results = asyncio.run(
            fetch_search_results(
                store=SupermarketStore.INTERMARCHE,
                queries=[str(query).strip() for query in queries if str(query).strip()],
                max_results=max_results,
                promotions_only=promotions_only,
            )
        )
        saved = upsert_search_cache(session, SupermarketStore.INTERMARCHE, results)
        return {"results": [row.model_dump(mode="json") for row in saved]}

    if action == "grocery.list_items":
        limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=500)
        statement = select(GroceryItem).order_by(GroceryItem.checked.asc(), GroceryItem.priority.asc()).limit(limit)
        if payload.get("checked") is not None:
            statement = statement.where(GroceryItem.checked == _as_bool(payload.get("checked")))

        items = session.exec(statement).all()
        return {"items": [item.model_dump(mode="json") for item in items]}

    if action == "grocery.update_item":
        item_id = int(payload.get("item_id", 0))
        item = session.get(GroceryItem, item_id)
        if not item:
            raise ValueError("item_id not found")

        was_checked = item.checked
        patch = GroceryItemUpdate.model_validate({k: v for k, v in payload.items() if k != "item_id"})
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No grocery fields to update")

        for key, value in updates.items():
            setattr(item, key, value)
        item.updated_at = now

        session.add(item)
        session.commit()
        session.refresh(item)
        pantry_sync = None
        if not was_checked and item.checked:
            pantry_sync = sync_checked_grocery_item_to_pantry(session, item)
        return {"item": item.model_dump(mode="json"), "pantry_sync": pantry_sync}

    if action == "grocery.check_item":
        item_id = int(payload.get("item_id", 0))
        checked = _as_bool(payload.get("checked"), default=True)
        item = session.get(GroceryItem, item_id)
        if not item:
            raise ValueError("item_id not found")
        was_checked = item.checked
        item.checked = checked
        item.updated_at = now
        session.add(item)
        session.commit()
        session.refresh(item)
        pantry_sync = None
        if not was_checked and item.checked:
            pantry_sync = sync_checked_grocery_item_to_pantry(session, item)
        return {"item": item.model_dump(mode="json"), "pantry_sync": pantry_sync}

    if action == "grocery.delete_item":
        item_id = int(payload.get("item_id", 0))
        item = session.get(GroceryItem, item_id)
        if not item:
            raise ValueError("item_id not found")
        sync_rows = session.exec(
            select(GroceryPantrySync).where(GroceryPantrySync.grocery_item_id == item_id)
        ).all()
        for row in sync_rows:
            session.delete(row)
        if sync_rows:
            session.commit()
        session.delete(item)
        session.commit()
        return {"ok": True, "deleted_id": item_id}

    if action == "video.fetch":
        url = str(payload.get("url") or "").strip()
        if not url:
          raise ValueError("url is required")
        return {"video": extract_video_source(url).model_dump(mode="json")}

    if action == "recipe.add":
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
        )
        session.add(recipe)
        session.commit()
        session.refresh(recipe)

        for ing in data.ingredients:
            ingredient = RecipeIngredient(recipe_id=recipe.id, **ing.model_dump())
            session.add(ingredient)
        session.commit()

        recipe = session.get(Recipe, recipe.id)
        return {"recipe": build_recipe_read(session, recipe).model_dump(mode="json")}

    if action == "recipe.update":
        recipe_id = int(payload.get("recipe_id", 0))
        recipe = session.get(Recipe, recipe_id)
        if not recipe:
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
                ingredient = RecipeIngredient(recipe_id=recipe.id, **ing.model_dump())
                session.add(ingredient)
            recipe.updated_at = now
            session.add(recipe)
            session.commit()

        session.refresh(recipe)
        return {"recipe": build_recipe_read(session, recipe).model_dump(mode="json")}

    if action == "recipe.list":
        limit = _clamp_int(payload.get("limit"), default=20, minimum=1, maximum=100)
        recipes = session.exec(select(Recipe).order_by(Recipe.created_at.desc()).limit(limit)).all()
        data = [build_recipe_read(session, recipe).model_dump(mode="json") for recipe in recipes]
        return {"recipes": data}

    if action == "recipe.get":
        recipe_id = int(payload.get("recipe_id", 0))
        recipe = session.get(Recipe, recipe_id)
        if not recipe:
            raise ValueError("recipe_id not found")
        return {"recipe": build_recipe_read(session, recipe).model_dump(mode="json")}

    if action == "recipe.confirm_cooked":
        recipe_id = int(payload.get("recipe_id", 0))
        recipe = session.get(Recipe, recipe_id)
        if not recipe:
            raise ValueError("recipe_id not found")
        servings_override = _clamp_int(payload.get("servings_override"), default=None, minimum=1, maximum=100) if payload.get("servings_override") is not None else None
        missing = compute_recipe_missing_ingredients(session, recipe, servings_override)
        consumption = consume_recipe_ingredients(session, recipe, servings_override)
        return {
            "recipe_id": recipe.id,
            "recipe_name": recipe.name,
            "cooked_at": now,
            "note": payload.get("note"),
            "missing_ingredients": [item.model_dump(mode="json") for item in missing],
            "pantry_consumption": consumption,
        }

    if action == "recipe.delete":
        recipe_id = int(payload.get("recipe_id", 0))
        recipe = session.get(Recipe, recipe_id)
        if not recipe:
            raise ValueError("recipe_id not found")
        ingredient_rows = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)).all()
        for row in ingredient_rows:
            session.delete(row)
        if ingredient_rows:
            session.commit()

        meal_plans = session.exec(select(MealPlan).where(MealPlan.recipe_id == recipe.id)).all()
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

    if action == "meal_plan.add":
        data = MealPlanCreate.model_validate(payload)
        recipe = session.get(Recipe, data.recipe_id)
        if not recipe:
            raise ValueError("recipe_id not found")

        planned_at = _resolve_meal_planned_at(payload)
        plan = MealPlan(**data.model_dump(), planned_at=planned_at)
        if plan.planned_for is None:
            plan.planned_for = planned_at.date()
        session.add(plan)
        session.commit()
        session.refresh(plan)

        if plan.auto_add_missing_ingredients:
            sync_meal_plan_to_grocery(session, plan)
        return {"meal_plan": build_meal_plan_read(session, plan).model_dump(mode="json")}

    if action == "meal_plan.list":
        limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=400)
        statement = select(MealPlan).order_by(MealPlan.planned_at.asc()).limit(limit)
        if payload.get("date_from"):
            date_from = _parse_date(payload.get("date_from"), "date_from")
            statement = statement.where(MealPlan.planned_at >= datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc))
        if payload.get("date_to"):
            date_to = _parse_date(payload.get("date_to"), "date_to")
            statement = statement.where(MealPlan.planned_at <= datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc))
        if payload.get("slot"):
            statement = statement.where(MealPlan.slot == MealSlot(payload.get("slot")))
        plans = session.exec(statement).all()
        return {"meal_plans": [build_meal_plan_read(session, plan).model_dump(mode="json") for plan in plans]}

    if action == "meal_plan.update":
        meal_plan_id = int(payload.get("meal_plan_id", 0))
        plan = session.get(MealPlan, meal_plan_id)
        if not plan:
            raise ValueError("meal_plan_id not found")
        patch = MealPlanUpdate.model_validate({k: v for k, v in payload.items() if k != "meal_plan_id"})
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No meal plan fields to update")
        if "recipe_id" in updates and not session.get(Recipe, updates["recipe_id"]):
            raise ValueError("recipe_id not found")

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
        plan.planned_at = _resolve_meal_planned_at({**payload, **updates}, current=plan.planned_at)
        if plan.planned_for is None:
            plan.planned_for = plan.planned_at.date()
        if reset_cook_confirmation:
            confirmation = session.exec(
                select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == plan.id)
            ).first()
            if confirmation:
                session.delete(confirmation)
        plan.updated_at = now
        session.add(plan)
        session.commit()
        session.refresh(plan)
        return {"meal_plan": build_meal_plan_read(session, plan).model_dump(mode="json")}

    if action == "meal_plan.delete":
        meal_plan_id = int(payload.get("meal_plan_id", 0))
        plan = session.get(MealPlan, meal_plan_id)
        if not plan:
            raise ValueError("meal_plan_id not found")
        confirmation = session.exec(
            select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == plan.id)
        ).first()
        if confirmation:
            session.delete(confirmation)
            session.commit()
        session.delete(plan)
        session.commit()
        return {"ok": True, "deleted_id": meal_plan_id}

    if action == "meal_plan.sync_groceries":
        meal_plan_id = int(payload.get("meal_plan_id", 0))
        plan = session.get(MealPlan, meal_plan_id)
        if not plan:
            raise ValueError("meal_plan_id not found")
        created, missing = sync_meal_plan_to_grocery(session, plan)
        return {
            "meal_plan_id": meal_plan_id,
            "created_grocery_items": created,
            "missing_ingredients": [item.model_dump(mode="json") for item in missing],
        }

    if action == "meal_plan.confirm_cooked":
        meal_plan_id = int(payload.get("meal_plan_id", 0))
        plan = session.get(MealPlan, meal_plan_id)
        if not plan:
            raise ValueError("meal_plan_id not found")
        result = confirm_meal_plan_cooked(session, plan, note=payload.get("note"))
        return {
            "meal_plan_id": meal_plan_id,
            "already_confirmed": bool(result.get("already_confirmed")),
            "confirmed_at": result.get("confirmed_at"),
            "note": result.get("note"),
            "pantry_consumption": result.get("pantry_consumption", []),
        }

    if action == "meal_plan.log_cooked":
        recipe_id = int(payload.get("recipe_id", 0))
        recipe = session.get(Recipe, recipe_id)
        if not recipe:
            raise ValueError("recipe_id not found")
        cooked_at = _parse_datetime(payload.get("cooked_at"), "cooked_at") or now
        plan = MealPlan(
            recipe_id=recipe_id,
            planned_at=cooked_at,
            planned_for=cooked_at.date(),
            servings_override=payload.get("servings_override"),
            note=payload.get("note") or "cooked without explicit planning",
            auto_add_missing_ingredients=False,
        )
        session.add(plan)
        session.commit()
        session.refresh(plan)
        result = confirm_meal_plan_cooked(session, plan, note=payload.get("note"))
        return {
            "meal_plan": build_meal_plan_read(session, plan).model_dump(mode="json"),
            "confirmation": result,
        }

    if action == "meal_plan.unconfirm_cooked":
        meal_plan_id = int(payload.get("meal_plan_id", 0))
        plan = session.get(MealPlan, meal_plan_id)
        if not plan:
            raise ValueError("meal_plan_id not found")
        result = unconfirm_meal_plan_cooked(session, plan)
        return {
            "meal_plan_id": meal_plan_id,
            "already_unconfirmed": bool(result.get("already_unconfirmed")),
            "previously_confirmed_at": result.get("previously_confirmed_at"),
            "note": result.get("note"),
            "pantry_restore": result.get("pantry_restore", []),
        }

    if action == "calendar.add_item":
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

    if action == "calendar.list_items":
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

    if action == "calendar.update_item":
        item_id = int(payload.get("item_id", 0))
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

    if action == "calendar.delete_item":
        item_id = int(payload.get("item_id", 0))
        item = session.get(CalendarItem, item_id)
        if not item:
            raise ValueError("item_id not found")
        if item.generated:
            raise ValueError("Generated calendar items must be deleted from their source module")
        session.delete(item)
        session.commit()
        return {"ok": True, "deleted_id": item_id}

    if action == "calendar.agenda":
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

    if action == "calendar.sync":
        synced, removed, by_source = sync_generated_calendar_items(session)
        return {"synced": synced, "removed": removed, "generated_by_source": by_source, "synced_at": now.isoformat()}

    if action == "calendar.due_reminders":
        sync_generated_calendar_items(session)
        within_minutes = _clamp_int(payload.get("within_minutes"), default=30, minimum=1, maximum=1440)
        reminders = list_due_reminders(session, within_minutes=within_minutes)
        return {"reminders": [entry.model_dump(mode="json") for entry in reminders]}

    if action == "calendar.ack_reminder":
        item_id = int(payload.get("item_id", 0))
        item = session.get(CalendarItem, item_id)
        if not item:
            raise ValueError("item_id not found")
        item.last_notified_at = now
        item.updated_at = now
        session.add(item)
        session.commit()
        return {"ok": True, "item_id": item_id, "ack_at": now.isoformat()}

    if action == "habit.create":
        data = HabitCreate.model_validate(payload)
        habit = Habit(**data.model_dump())
        session.add(habit)
        session.commit()
        session.refresh(habit)
        return {"habit": habit.model_dump(mode="json")}

    if action == "habit.list":
        active_only = _as_bool(payload.get("active_only"), default=True)
        statement = select(Habit).order_by(Habit.created_at.desc())
        if active_only:
            statement = statement.where(Habit.active.is_(True))
        habits = session.exec(statement).all()
        return {"habits": [habit.model_dump(mode="json") for habit in habits]}

    if action == "habit.set_active":
        habit_id = int(payload.get("habit_id", 0))
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

    if action == "habit.log":
        habit_id = int(payload.get("habit_id", 0))
        habit = session.get(Habit, habit_id)
        if not habit:
            raise ValueError("habit_id not found")

        log = HabitLog(
            habit_id=habit_id,
            value=int(payload.get("value", 1)),
            note=payload.get("note"),
        )
        session.add(log)
        session.commit()
        session.refresh(log)

        streak = update_habit_streak(session, habit_id)
        return {"log": log.model_dump(mode="json"), "streak": streak}

    if action == "habit.list_logs":
        habit_id = int(payload.get("habit_id", 0))
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

    if action == "goal.create":
        data = GoalCreate.model_validate(payload)
        goal = Goal(**data.model_dump())
        session.add(goal)
        session.commit()
        session.refresh(goal)
        return {"goal": goal.model_dump(mode="json")}

    if action == "goal.list":
        limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=300)
        statement = select(Goal).order_by(Goal.created_at.desc()).limit(limit)
        if payload.get("status"):
            statement = statement.where(Goal.status == GoalStatus(payload["status"]))
        goals = session.exec(statement).all()
        return {"goals": [goal.model_dump(mode="json") for goal in goals]}

    if action == "goal.get":
        goal_id = int(payload.get("goal_id", 0))
        goal = session.get(Goal, goal_id)
        if not goal:
            raise ValueError("goal_id not found")
        return {"goal": goal.model_dump(mode="json")}

    if action == "goal.update":
        goal_id = int(payload.get("goal_id", 0))
        goal = session.get(Goal, goal_id)
        if not goal:
            raise ValueError("goal_id not found")

        patch = GoalUpdate.model_validate({k: v for k, v in payload.items() if k != "goal_id"})
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No goal fields to update")

        for key, value in updates.items():
            setattr(goal, key, value)
        goal.updated_at = now

        session.add(goal)
        session.commit()
        session.refresh(goal)
        return {"goal": goal.model_dump(mode="json")}

    if action == "goal.add_milestone":
        goal_id = int(payload.get("goal_id", 0))
        goal = session.get(Goal, goal_id)
        if not goal:
            raise ValueError("goal_id not found")

        data = GoalMilestoneCreate.model_validate({k: v for k, v in payload.items() if k != "goal_id"})
        milestone = GoalMilestone(goal_id=goal_id, **data.model_dump())
        session.add(milestone)
        session.commit()
        session.refresh(milestone)
        return {"milestone": milestone.model_dump(mode="json")}

    if action == "goal.list_milestones":
        goal_id = int(payload.get("goal_id", 0))
        goal = session.get(Goal, goal_id)
        if not goal:
            raise ValueError("goal_id not found")

        limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=500)
        milestones = session.exec(
            select(GoalMilestone)
            .where(GoalMilestone.goal_id == goal_id)
            .order_by(GoalMilestone.created_at.desc())
            .limit(limit)
        ).all()
        return {"milestones": [item.model_dump(mode="json") for item in milestones]}

    if action == "goal.update_milestone":
        goal_id = int(payload.get("goal_id", 0))
        milestone_id = int(payload.get("milestone_id", 0))
        goal = session.get(Goal, goal_id)
        if not goal:
            raise ValueError("goal_id not found")

        milestone = session.get(GoalMilestone, milestone_id)
        if not milestone or milestone.goal_id != goal_id:
            raise ValueError("milestone_id not found")

        patch = GoalMilestoneUpdate.model_validate(
            {k: v for k, v in payload.items() if k not in {"goal_id", "milestone_id"}}
        )
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No milestone fields to update")

        for key, value in updates.items():
            setattr(milestone, key, value)
        if patch.completed is True and milestone.completed_at is None:
            milestone.completed_at = now
        if patch.completed is False:
            milestone.completed_at = None

        session.add(milestone)
        session.commit()
        session.refresh(milestone)
        return {"milestone": milestone.model_dump(mode="json")}

    if action == "event.create":
        data = EventCreate.model_validate(payload)
        if data.end_at <= data.start_at:
            raise ValueError("end_at must be after start_at")
        event = CalendarEvent(**data.model_dump())
        session.add(event)
        session.commit()
        session.refresh(event)
        return {"event": event.model_dump(mode="json")}

    if action == "event.list":
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

    if action == "event.upcoming":
        days = _clamp_int(payload.get("days"), default=7, minimum=1, maximum=365)
        event_type = EventType(payload["type"]) if payload.get("type") else None
        events = list_upcoming_events(session, days=days, event_type=event_type)
        return {"events": [event.model_dump(mode="json") for event in events]}

    if action == "event.get":
        event_id = int(payload.get("event_id", 0))
        event = session.get(CalendarEvent, event_id)
        if not event:
            raise ValueError("event_id not found")
        return {"event": event.model_dump(mode="json")}

    if action == "event.update":
        event_id = int(payload.get("event_id", 0))
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
        event.updated_at = now

        session.add(event)
        session.commit()
        session.refresh(event)
        return {"event": event.model_dump(mode="json")}

    if action == "event.delete":
        event_id = int(payload.get("event_id", 0))
        event = session.get(CalendarEvent, event_id)
        if not event:
            raise ValueError("event_id not found")
        session.delete(event)
        session.commit()
        return {"ok": True, "deleted_id": event_id}

    if action == "subscription.create":
        data = SubscriptionCreate.model_validate(payload)
        subscription = Subscription(**data.model_dump())
        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        return {"subscription": subscription.model_dump(mode="json")}

    if action == "subscription.list":
        limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=500)
        active_only = _as_bool(payload.get("active_only"), default=True)
        statement = select(Subscription).order_by(Subscription.next_due_date.asc()).limit(limit)
        if active_only:
            statement = statement.where(Subscription.active.is_(True))
        subscriptions = session.exec(statement).all()
        return {"subscriptions": [item.model_dump(mode="json") for item in subscriptions]}

    if action == "subscription.get":
        subscription_id = int(payload.get("subscription_id", 0))
        subscription = session.get(Subscription, subscription_id)
        if not subscription:
            raise ValueError("subscription_id not found")
        return {"subscription": subscription.model_dump(mode="json")}

    if action == "subscription.update":
        subscription_id = int(payload.get("subscription_id", 0))
        subscription = session.get(Subscription, subscription_id)
        if not subscription:
            raise ValueError("subscription_id not found")

        patch = SubscriptionUpdate.model_validate({k: v for k, v in payload.items() if k != "subscription_id"})
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No subscription fields to update")

        for key, value in updates.items():
            setattr(subscription, key, value)
        subscription.updated_at = now

        session.add(subscription)
        session.commit()
        session.refresh(subscription)
        return {"subscription": subscription.model_dump(mode="json")}

    if action == "subscription.upcoming":
        days = _clamp_int(payload.get("days"), default=30, minimum=1, maximum=365)
        subscriptions = list_upcoming_subscriptions(session, days=days)
        return {"subscriptions": [item.model_dump(mode="json") for item in subscriptions]}

    if action == "subscription.projection":
        currency = payload.get("currency", "EUR")
        projection = build_subscription_projection(session, currency=currency)
        return {"projection": projection.model_dump(mode="json")}

    if action == "patrimony.overview":
        accounts = session.exec(
            select(Account).where(Account.is_active.is_(True)).order_by(Account.name.asc())
        ).all()
        goals = session.exec(select(SavingsGoal).order_by(SavingsGoal.target_date.asc())).all()
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

    if action == "patrimony.list_accounts":
        active_only = _as_bool(payload.get("active_only"), default=True)
        statement = select(Account).order_by(Account.name.asc())
        if active_only:
            statement = statement.where(Account.is_active.is_(True))
        rows = session.exec(statement).all()
        return {"accounts": [_build_account_read_payload(row) for row in rows]}

    if action == "patrimony.add_account":
        data = AccountCreate.model_validate(payload)
        row = Account(**data.model_dump())
        session.add(row)
        session.commit()
        session.refresh(row)
        return {"account": _build_account_read_payload(row)}

    if action == "patrimony.update_account":
        account_id = int(payload.get("account_id", 0))
        row = session.get(Account, account_id)
        if not row:
            raise ValueError("account_id not found")
        patch = AccountUpdate.model_validate(
            {k: v for k, v in payload.items() if k != "account_id"}
        )
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No patrimony account fields to update")
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        return {"account": _build_account_read_payload(row)}

    if action == "patrimony.delete_account":
        account_id = int(payload.get("account_id", 0))
        row = session.get(Account, account_id)
        if not row:
            raise ValueError("account_id not found")
        session.delete(row)
        session.commit()
        return {"ok": True, "deleted_id": account_id}

    if action == "patrimony.list_goals":
        goals = session.exec(select(SavingsGoal).order_by(SavingsGoal.target_date.asc())).all()
        accounts_by_id = {
            account.id: account
            for account in session.exec(select(Account)).all()
            if account.id is not None
        }
        return {
            "goals": [
                _build_savings_goal_read_payload(goal, accounts_by_id) for goal in goals
            ]
        }

    if action == "patrimony.add_goal":
        data = SavingsGoalCreate.model_validate(payload)
        row = SavingsGoal(**data.model_dump())
        session.add(row)
        session.commit()
        session.refresh(row)
        accounts_by_id = {
            account.id: account
            for account in session.exec(select(Account)).all()
            if account.id is not None
        }
        return {"goal": _build_savings_goal_read_payload(row, accounts_by_id)}

    if action == "patrimony.update_goal":
        goal_id = int(payload.get("goal_id", 0))
        row = session.get(SavingsGoal, goal_id)
        if not row:
            raise ValueError("goal_id not found")
        patch = SavingsGoalUpdate.model_validate(
            {k: v for k, v in payload.items() if k != "goal_id"}
        )
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No patrimony goal fields to update")
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = now
        session.add(row)
        session.commit()
        session.refresh(row)
        accounts_by_id = {
            account.id: account
            for account in session.exec(select(Account)).all()
            if account.id is not None
        }
        return {"goal": _build_savings_goal_read_payload(row, accounts_by_id)}

    if action == "patrimony.delete_goal":
        goal_id = int(payload.get("goal_id", 0))
        row = session.get(SavingsGoal, goal_id)
        if not row:
            raise ValueError("goal_id not found")
        session.delete(row)
        session.commit()
        return {"ok": True, "deleted_id": goal_id}

    if action == "pantry.add_item":
        data = PantryItemCreate.model_validate(payload)
        item = PantryItem(**data.model_dump())
        session.add(item)
        session.commit()
        session.refresh(item)
        return {"item": item.model_dump(mode="json")}

    if action == "pantry.list_items":
        limit = _clamp_int(payload.get("limit"), default=500, minimum=1, maximum=1000)
        low_stock_only = _as_bool(payload.get("low_stock_only"), default=False)
        expiring_in_days = payload.get("expiring_in_days")

        statement = select(PantryItem).order_by(PantryItem.updated_at.desc()).limit(limit)
        if low_stock_only:
            statement = statement.where(PantryItem.quantity <= PantryItem.min_quantity)
        if expiring_in_days is not None:
            days = _clamp_int(expiring_in_days, default=7, minimum=1, maximum=3650)
            until = date.today() + timedelta(days=days)
            statement = statement.where(PantryItem.expires_at.is_not(None), PantryItem.expires_at <= until)

        items = session.exec(statement).all()
        return {"items": [item.model_dump(mode="json") for item in items]}

    if action == "pantry.update_item":
        item_id = int(payload.get("item_id", 0))
        item = session.get(PantryItem, item_id)
        if not item:
            raise ValueError("item_id not found")

        patch = PantryItemUpdate.model_validate({k: v for k, v in payload.items() if k != "item_id"})
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No pantry fields to update")

        for key, value in updates.items():
            setattr(item, key, value)
        item.updated_at = now

        session.add(item)
        session.commit()
        session.refresh(item)
        return {"item": item.model_dump(mode="json")}

    if action == "pantry.consume_item":
        item_id = int(payload.get("item_id", 0))
        amount = float(payload.get("amount", 0))
        if amount <= 0:
            raise ValueError("amount must be > 0")

        item = session.get(PantryItem, item_id)
        if not item:
            raise ValueError("item_id not found")

        item.quantity = max(0.0, item.quantity - amount)
        item.updated_at = now
        session.add(item)
        session.commit()
        session.refresh(item)
        return {"item": item.model_dump(mode="json")}

    if action == "pantry.delete_item":
        item_id = int(payload.get("item_id", 0))
        item = session.get(PantryItem, item_id)
        if not item:
            raise ValueError("item_id not found")
        sync_rows = session.exec(
            select(GroceryPantrySync).where(GroceryPantrySync.pantry_item_id == item_id)
        ).all()
        for row in sync_rows:
            session.delete(row)
        if sync_rows:
            session.commit()
        session.delete(item)
        session.commit()
        return {"ok": True, "deleted_id": item_id}

    if action == "pantry.overview":
        days = _clamp_int(payload.get("days"), default=7, minimum=1, maximum=365)
        overview = build_pantry_overview(session, days=days)
        return {"overview": overview.model_dump(mode="json")}

    if action == "note.create":
        data = NoteCreate.model_validate(payload)
        note = Note(**data.model_dump())
        session.add(note)
        session.commit()
        session.refresh(note)
        return {"note": note.model_dump(mode="json")}

    if action == "note.list":
        limit = _clamp_int(payload.get("limit"), default=300, minimum=1, maximum=1000)
        statement = select(Note).order_by(Note.pinned.desc(), Note.updated_at.desc()).limit(limit)
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

    if action == "note.get":
        note_id = int(payload.get("note_id", 0))
        note = session.get(Note, note_id)
        if not note:
            raise ValueError("note_id not found")
        return {"note": note.model_dump(mode="json")}

    if action == "note.update":
        note_id = int(payload.get("note_id", 0))
        note = session.get(Note, note_id)
        if not note:
            raise ValueError("note_id not found")

        patch = NoteUpdate.model_validate({k: v for k, v in payload.items() if k != "note_id"})
        updates = patch.model_dump(exclude_unset=True)
        if not updates:
            raise ValueError("No note fields to update")

        for key, value in updates.items():
            setattr(note, key, value)
        note.updated_at = now
        session.add(note)
        session.commit()
        session.refresh(note)
        return {"note": note.model_dump(mode="json")}

    if action == "note.delete":
        note_id = int(payload.get("note_id", 0))
        note = session.get(Note, note_id)
        if not note:
            raise ValueError("note_id not found")

        session.delete(note)
        session.commit()
        return {"ok": True, "deleted_id": note_id}

    if action == "note.journal":
        limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=1000)
        statement = select(Note).where(Note.kind == NoteKind.JOURNAL).order_by(Note.created_at.desc()).limit(limit)
        notes = session.exec(statement).all()

        from_date = _parse_date(payload.get("from_date"), "from_date")
        to_date = _parse_date(payload.get("to_date"), "to_date")
        if from_date:
            notes = [note for note in notes if note.created_at.date() >= from_date]
        if to_date:
            notes = [note for note in notes if note.created_at.date() <= to_date]

        return {"notes": [note.model_dump(mode="json") for note in notes]}

    if action == "linear.projects":
        source = str(payload.get("source", "cache")).lower()
        limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=500)
        if source == "live":
            try:
                projects = fetch_linear_projects_live()[:limit]
            except LinearIntegrationError as exc:
                raise ValueError(str(exc)) from exc
            return {"projects": [item.model_dump(mode="json") for item in projects]}

        rows = session.exec(select(LinearProjectCache).order_by(LinearProjectCache.name.asc()).limit(limit)).all()
        return {
            "projects": [
                {
                    "id": row.linear_id,
                    "name": row.name,
                    "key": row.key,
                    "state": row.state,
                    "description": row.description,
                    "url": row.url,
                }
                for row in rows
            ]
        }

    if action == "linear.issues":
        source = str(payload.get("source", "cache")).lower()
        project_id = payload.get("project_id")
        limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=500)
        if source == "live":
            try:
                issues = fetch_linear_issues_live(project_id=project_id, limit=limit)
            except LinearIntegrationError as exc:
                raise ValueError(str(exc)) from exc
            return {"issues": [item.model_dump(mode="json") for item in issues]}

        statement = select(LinearIssueCache).order_by(LinearIssueCache.synced_at.desc()).limit(limit)
        if project_id:
            statement = statement.where(LinearIssueCache.project_linear_id == project_id)
        rows = session.exec(statement).all()
        return {
            "issues": [
                {
                    "id": row.linear_id,
                    "identifier": row.identifier,
                    "title": row.title,
                    "state": row.state,
                    "priority": row.priority,
                    "due_date": row.due_date.isoformat() if row.due_date else None,
                    "assignee_name": row.assignee_name,
                    "project_id": row.project_linear_id,
                    "url": row.url,
                }
                for row in rows
            ]
        }

    if action == "linear.issue_create":
        data = LinearIssueCreate.model_validate(payload)
        try:
            issue = create_linear_issue_live(data)
        except LinearIntegrationError as exc:
            raise ValueError(str(exc)) from exc
        cache_row = LinearIssueCache(
            linear_id=issue.id,
            identifier=issue.identifier,
            title=issue.title,
            state=issue.state,
            priority=issue.priority,
            due_date=issue.due_date,
            assignee_name=issue.assignee_name,
            project_linear_id=issue.project_id,
            url=issue.url,
            synced_at=now,
        )
        session.add(cache_row)
        session.commit()
        return {"issue": issue.model_dump(mode="json")}

    if action == "linear.sync":
        project_id = payload.get("project_id")
        try:
            projects, issues = sync_linear_cache(session, project_id=project_id)
        except LinearIntegrationError as exc:
            raise ValueError(str(exc)) from exc
        return {"projects": projects, "issues": issues, "synced_at": now.isoformat()}

    if action == "dashboard.overview":
        return {"overview": build_dashboard_overview(session).model_dump(mode="json")}

    raise ValueError(f"Unknown action: {action}")
