from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Column, String
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AccountType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    INVESTMENT = "investment"
    CRYPTO = "crypto"
    OTHER = "other"


class SupermarketStore(str, Enum):
    INTERMARCHE = "intermarche"


class SupermarketTargetType(str, Enum):
    RECIPE_INGREDIENT = "recipe_ingredient"
    PANTRY_ITEM = "pantry_item"


class TransactionKind(str, Enum):
    EXPENSE = "expense"
    INCOME = "income"


class HabitFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"


class TaskScheduleMode(str, Enum):
    NONE = "none"
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


class FitnessSessionType(str, Enum):
    STRENGTH = "strength"
    CARDIO = "cardio"
    MOBILITY = "mobility"
    RECOVERY = "recovery"
    MIXED = "mixed"


class FitnessSessionStatus(str, Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    SKIPPED = "skipped"


class FitnessExerciseMode(str, Enum):
    REPS = "reps"
    DURATION = "duration"


class GoalStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class EventType(str, Enum):
    PERSONAL = "personal"
    WORK = "work"
    HEALTH = "health"
    FINANCE = "finance"
    SOCIAL = "social"


class SubscriptionInterval(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class NoteKind(str, Enum):
    NOTE = "note"
    JOURNAL = "journal"
    IDEA = "idea"


class MealSlot(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"


class CalendarCategory(str, Enum):
    GENERAL = "general"
    TASK = "task"
    EVENT = "event"
    SUBSCRIPTION = "subscription"
    MEAL = "meal"


class CalendarSource(str, Enum):
    MANUAL = "manual"
    TASK = "task"
    HABIT = "habit"
    EVENT = "event"
    SUBSCRIPTION = "subscription"
    MEAL_PLAN = "meal_plan"
    FITNESS_SESSION = "fitness_session"


class CalendarFeed(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    token: str = Field(sa_column=Column(String, unique=True, nullable=False, index=True))
    sources: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    include_completed: bool = True
    active: bool = True
    last_accessed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = None
    subtasks: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    status: TaskStatus = Field(default=TaskStatus.TODO)
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    schedule_mode: TaskScheduleMode = Field(default=TaskScheduleMode.NONE)
    schedule_time: str | None = Field(default=None, max_length=5)
    schedule_weekday: int | None = Field(default=None, ge=0, le=6)
    due_at: datetime | None = None
    estimated_minutes: int | None = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class FinanceTransaction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    kind: TransactionKind
    amount: float
    currency: str = Field(default="EUR", max_length=8)
    category: str
    note: str | None = None
    occurred_at: datetime = Field(default_factory=utcnow)
    is_recurring: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Budget(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    month: str
    category: str
    monthly_limit: float
    currency: str = Field(default="EUR", max_length=8)
    alert_threshold: float = 0.8
    created_at: datetime = Field(default_factory=utcnow)


class GroceryItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    quantity: float = 1
    unit: str = "item"
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = Field(default=None, index=True)
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    checked: bool = False
    priority: int = 3
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class GroceryPantrySync(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    grocery_item_id: int = Field(foreign_key="groceryitem.id", index=True)
    pantry_item_id: int = Field(foreign_key="pantryitem.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)


class Recipe(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None
    instructions: str
    steps: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    utensils: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    prep_minutes: int = 0
    cook_minutes: int = 0
    servings: int = 1
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    source_url: str | None = None
    source_platform: str | None = None
    source_title: str | None = None
    source_description: str | None = None
    source_transcript: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class RecipeIngredient(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    name: str
    quantity: float = 1
    unit: str = "item"
    note: str | None = None
    store: SupermarketStore | None = None
    store_label: str | None = None
    external_id: str | None = Field(default=None, index=True)
    category: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    image_url: str | None = None


class MealPlan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    planned_at: datetime = Field(default_factory=utcnow)
    # Legacy fields kept nullable for backward compatibility with old clients/data.
    planned_for: date | None = None
    slot: MealSlot | None = None
    recipe_id: int = Field(foreign_key="recipe.id", index=True)
    servings_override: int | None = None
    note: str | None = None
    auto_add_missing_ingredients: bool = True
    synced_grocery_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class MealPlanCookConfirmation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    meal_plan_id: int = Field(foreign_key="mealplan.id", index=True, unique=True)
    confirmed_at: datetime = Field(default_factory=utcnow)
    note: str | None = None
    pantry_consumption: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Habit(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None
    frequency: HabitFrequency = HabitFrequency.DAILY
    target_per_period: int = 1
    schedule_time: str | None = Field(default=None, max_length=5)
    schedule_times: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    schedule_weekday: int | None = Field(default=None, ge=0, le=6)
    schedule_weekdays: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    duration_minutes: int = 30
    streak: int = 0
    active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class HabitLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    habit_id: int = Field(foreign_key="habit.id", index=True)
    logged_at: datetime = Field(default_factory=utcnow)
    value: int = 1
    note: str | None = None


class FitnessSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    session_type: FitnessSessionType = FitnessSessionType.MIXED
    planned_at: datetime = Field(default_factory=utcnow, index=True)
    duration_minutes: int = 45
    exercises: list[dict | str] = Field(default_factory=list, sa_column=Column(JSON))
    note: str | None = None
    status: FitnessSessionStatus = FitnessSessionStatus.PLANNED
    completed_at: datetime | None = None
    actual_duration_minutes: int | None = None
    effort_rating: int | None = Field(default=None, ge=1, le=10)
    calories_burned: float | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class FitnessMeasurement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    recorded_at: datetime = Field(default_factory=utcnow, index=True)
    body_weight_kg: float | None = None
    body_fat_pct: float | None = None
    resting_hr: int | None = None
    sleep_hours: float | None = None
    steps: int | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Goal(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = None
    status: GoalStatus = GoalStatus.PLANNED
    progress_percent: int = Field(default=0, ge=0, le=100)
    target_date: date | None = None
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class GoalMilestone(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    goal_id: int = Field(foreign_key="goal.id", index=True)
    title: str
    due_at: datetime | None = None
    completed: bool = False
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class CalendarEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    location: str | None = None
    type: EventType = EventType.PERSONAL
    all_day: bool = False
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Subscription(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    category: str = "general"
    amount: float
    currency: str = Field(default="EUR", max_length=8)
    interval: SubscriptionInterval = SubscriptionInterval.MONTHLY
    next_due_date: date
    autopay: bool = False
    active: bool = True
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PantryItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    quantity: float = 0
    unit: str = "item"
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = Field(default=None, index=True)
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    min_quantity: float = 0
    expires_at: date | None = None
    location: str | None = None
    note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Note(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    content: str
    kind: NoteKind = NoteKind.NOTE
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    pinned: bool = False
    mood: int | None = Field(default=None, ge=1, le=10)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class CalendarItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    category: CalendarCategory = CalendarCategory.GENERAL
    source: CalendarSource = CalendarSource.MANUAL
    source_ref_id: int | None = Field(default=None, index=True)
    generated: bool = False
    completed: bool = False
    notification_enabled: bool = True
    reminder_offsets_min: list[int] = Field(default_factory=lambda: [60], sa_column=Column(JSON))
    extra_data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    last_notified_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class LinearProjectCache(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    linear_id: str = Field(index=True)
    name: str
    key: str | None = None
    state: str | None = None
    description: str | None = None
    url: str | None = None
    synced_at: datetime = Field(default_factory=utcnow)


class LinearIssueCache(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    linear_id: str = Field(index=True)
    identifier: str | None = Field(default=None, index=True)
    title: str
    state: str | None = None
    priority: int | None = None
    due_date: date | None = None
    assignee_name: str | None = None
    project_linear_id: str | None = Field(default=None, index=True)
    url: str | None = None
    synced_at: datetime = Field(default_factory=utcnow)


class SupermarketProduct(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    packaging: str | None = None
    price: str | None = None
    image_url: str | None = None
    store: str
    external_id: str | None = Field(default=None, index=True)
    category: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SupermarketSearchCache(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    store: SupermarketStore = Field(index=True)
    query: str = Field(index=True)
    external_id: str | None = Field(default=None, index=True)
    name: str
    brand: str | None = None
    category: str | None = None
    packaging: str | None = None
    price_amount: float | None = None
    price_text: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    payload_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utcnow, index=True)
    expires_at: datetime = Field(default_factory=utcnow, index=True)


class SupermarketMapping(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    target_type: SupermarketTargetType = Field(index=True)
    target_id: int = Field(index=True)
    store: SupermarketStore = Field(index=True)
    external_id: str
    store_label: str
    name_snapshot: str
    category_snapshot: str | None = None
    packaging_snapshot: str | None = None
    price_snapshot: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    last_verified_at: datetime = Field(default_factory=utcnow)
    active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    account_type: AccountType = AccountType.SAVINGS
    balance: float = 0.0
    currency: str = Field(default="EUR", max_length=8)
    institution: str | None = None
    note: str | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SavingsGoal(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    target_amount: float
    current_amount: float = 0.0
    currency: str = Field(default="EUR", max_length=8)
    target_date: date | None = None
    account_id: int | None = Field(default=None, foreign_key="account.id", index=True)
    note: str | None = None
    completed: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
