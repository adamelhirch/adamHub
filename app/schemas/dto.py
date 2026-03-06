from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    EventType,
    GoalStatus,
    HabitFrequency,
    CalendarCategory,
    CalendarSource,
    MealSlot,
    NoteKind,
    SubscriptionInterval,
    TaskPriority,
    TaskStatus,
    TransactionKind,
)


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    due_at: datetime | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_minutes: int | None = None
    tags: list[str] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_at: datetime | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    estimated_minutes: int | None = None
    tags: list[str] | None = None


class TaskRead(BaseModel):
    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_at: datetime | None
    estimated_minutes: int | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class FinanceTransactionCreate(BaseModel):
    kind: TransactionKind
    amount: float
    currency: str = "EUR"
    category: str
    note: str | None = None
    occurred_at: datetime | None = None
    is_recurring: bool = False


class FinanceTransactionRead(BaseModel):
    id: int
    kind: TransactionKind
    amount: float
    currency: str
    category: str
    note: str | None
    occurred_at: datetime
    is_recurring: bool
    created_at: datetime


class BudgetCreate(BaseModel):
    month: str = Field(description="Format YYYY-MM")
    category: str
    monthly_limit: float
    currency: str = "EUR"
    alert_threshold: float = 0.8


class BudgetRead(BaseModel):
    id: int
    month: str
    category: str
    monthly_limit: float
    currency: str
    alert_threshold: float
    created_at: datetime


class CategoryBudgetAnalytics(BaseModel):
    category: str
    spent: float
    limit: float
    remaining: float
    percentage_used: float
    status: str


class FinanceMonthSummary(BaseModel):
    year: int
    month: int
    income: float
    expense: float
    net: float
    expense_by_category: dict[str, float]
    budgets: list[CategoryBudgetAnalytics]


class GroceryItemCreate(BaseModel):
    name: str
    quantity: float = 1
    unit: str = "item"
    category: str | None = None
    priority: int = 3
    note: str | None = None


class GroceryItemUpdate(BaseModel):
    quantity: float | None = None
    unit: str | None = None
    category: str | None = None
    checked: bool | None = None
    priority: int | None = None
    note: str | None = None


class GroceryItemRead(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    category: str | None
    checked: bool
    priority: int
    note: str | None
    created_at: datetime
    updated_at: datetime


class RecipeIngredientIn(BaseModel):
    name: str
    quantity: float = 1
    unit: str = "item"
    note: str | None = None


class RecipeIngredientRead(BaseModel):
    id: int
    recipe_id: int
    name: str
    quantity: float
    unit: str
    note: str | None


class RecipeCreate(BaseModel):
    name: str
    description: str | None = None
    instructions: str
    prep_minutes: int = 0
    cook_minutes: int = 0
    servings: int = 1
    tags: list[str] = Field(default_factory=list)
    ingredients: list[RecipeIngredientIn] = Field(default_factory=list)


class RecipeRead(BaseModel):
    id: int
    name: str
    description: str | None
    instructions: str
    prep_minutes: int
    cook_minutes: int
    servings: int
    tags: list[str]
    ingredients: list[RecipeIngredientRead]
    created_at: datetime
    updated_at: datetime


class MissingIngredientRead(BaseModel):
    name: str
    needed_quantity: float
    available_quantity: float
    missing_quantity: float
    unit: str


class MealPlanCreate(BaseModel):
    planned_for: date
    slot: MealSlot
    recipe_id: int
    servings_override: int | None = Field(default=None, ge=1, le=100)
    note: str | None = None
    auto_add_missing_ingredients: bool = True


class MealPlanUpdate(BaseModel):
    planned_for: date | None = None
    slot: MealSlot | None = None
    recipe_id: int | None = None
    servings_override: int | None = Field(default=None, ge=1, le=100)
    note: str | None = None
    auto_add_missing_ingredients: bool | None = None


class MealPlanRead(BaseModel):
    id: int
    planned_for: date
    slot: MealSlot
    recipe_id: int
    recipe_name: str
    servings_override: int | None
    note: str | None
    auto_add_missing_ingredients: bool
    synced_grocery_at: datetime | None
    cooked: bool
    cooked_at: datetime | None
    cooked_note: str | None
    missing_ingredients: list[MissingIngredientRead]
    created_at: datetime
    updated_at: datetime


class MealPlanConfirmCooked(BaseModel):
    note: str | None = None


class MealIngredientConsumptionRead(BaseModel):
    name: str
    unit: str
    required_quantity: float
    consumed_quantity: float
    missing_quantity: float


class MealPlanConfirmResult(BaseModel):
    meal_plan_id: int
    already_confirmed: bool
    confirmed_at: datetime
    note: str | None
    pantry_consumption: list[MealIngredientConsumptionRead]


class MealIngredientRestoreRead(BaseModel):
    name: str
    unit: str
    restored_quantity: float
    pantry_item_id: int


class MealPlanUnconfirmResult(BaseModel):
    meal_plan_id: int
    already_unconfirmed: bool
    previously_confirmed_at: datetime | None
    note: str | None
    pantry_restore: list[MealIngredientRestoreRead]


class HabitCreate(BaseModel):
    name: str
    description: str | None = None
    frequency: HabitFrequency = HabitFrequency.DAILY
    target_per_period: int = 1


class HabitRead(BaseModel):
    id: int
    name: str
    description: str | None
    frequency: HabitFrequency
    target_per_period: int
    streak: int
    active: bool
    created_at: datetime
    updated_at: datetime


class HabitLogCreate(BaseModel):
    value: int = 1
    note: str | None = None


class HabitLogRead(BaseModel):
    id: int
    habit_id: int
    logged_at: datetime
    value: int
    note: str | None


class GoalCreate(BaseModel):
    title: str
    description: str | None = None
    status: GoalStatus = GoalStatus.PLANNED
    progress_percent: int = Field(default=0, ge=0, le=100)
    target_date: date | None = None
    tags: list[str] = Field(default_factory=list)


class GoalUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: GoalStatus | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    target_date: date | None = None
    tags: list[str] | None = None


class GoalRead(BaseModel):
    id: int
    title: str
    description: str | None
    status: GoalStatus
    progress_percent: int
    target_date: date | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class GoalMilestoneCreate(BaseModel):
    title: str
    due_at: datetime | None = None


class GoalMilestoneUpdate(BaseModel):
    title: str | None = None
    due_at: datetime | None = None
    completed: bool | None = None


class GoalMilestoneRead(BaseModel):
    id: int
    goal_id: int
    title: str
    due_at: datetime | None
    completed: bool
    completed_at: datetime | None
    created_at: datetime


class EventCreate(BaseModel):
    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    location: str | None = None
    type: EventType = EventType.PERSONAL
    all_day: bool = False
    tags: list[str] = Field(default_factory=list)


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = None
    type: EventType | None = None
    all_day: bool | None = None
    tags: list[str] | None = None


class EventRead(BaseModel):
    id: int
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    location: str | None
    type: EventType
    all_day: bool
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class CalendarItemCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str
    description: str | None = None
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    category: CalendarCategory = CalendarCategory.GENERAL
    notification_enabled: bool = True
    reminder_offsets_min: list[int] = Field(default_factory=lambda: [60])
    extra_data: dict = Field(default_factory=dict, validation_alias="metadata", serialization_alias="metadata")


class CalendarItemUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    category: CalendarCategory | None = None
    completed: bool | None = None
    notification_enabled: bool | None = None
    reminder_offsets_min: list[int] | None = None
    extra_data: dict | None = Field(default=None, validation_alias="metadata", serialization_alias="metadata")


class CalendarItemRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    title: str
    description: str | None
    start_at: datetime
    end_at: datetime
    all_day: bool
    category: CalendarCategory
    source: CalendarSource
    source_ref_id: int | None
    generated: bool
    completed: bool
    notification_enabled: bool
    reminder_offsets_min: list[int]
    extra_data: dict = Field(validation_alias="extra_data", serialization_alias="metadata")
    last_notified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CalendarSyncResult(BaseModel):
    synced: int
    removed: int
    generated_by_source: dict[str, int]
    synced_at: datetime


class CalendarReminderRead(BaseModel):
    item: CalendarItemRead
    due_at: datetime
    minutes_before: int


class SubscriptionCreate(BaseModel):
    name: str
    category: str = "general"
    amount: float
    currency: str = "EUR"
    interval: SubscriptionInterval = SubscriptionInterval.MONTHLY
    next_due_date: date
    autopay: bool = False
    active: bool = True
    note: str | None = None


class SubscriptionUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    amount: float | None = None
    currency: str | None = None
    interval: SubscriptionInterval | None = None
    next_due_date: date | None = None
    autopay: bool | None = None
    active: bool | None = None
    note: str | None = None


class SubscriptionRead(BaseModel):
    id: int
    name: str
    category: str
    amount: float
    currency: str
    interval: SubscriptionInterval
    next_due_date: date
    autopay: bool
    active: bool
    note: str | None
    created_at: datetime
    updated_at: datetime


class SubscriptionProjection(BaseModel):
    monthly_total: float
    yearly_total: float
    currency: str


class PantryItemCreate(BaseModel):
    name: str
    quantity: float = 0
    unit: str = "item"
    category: str | None = None
    min_quantity: float = 0
    expires_at: date | None = None
    location: str | None = None
    note: str | None = None


class PantryItemUpdate(BaseModel):
    quantity: float | None = None
    unit: str | None = None
    category: str | None = None
    min_quantity: float | None = None
    expires_at: date | None = None
    location: str | None = None
    note: str | None = None


class PantryConsume(BaseModel):
    amount: float = Field(gt=0)


class PantryItemRead(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    category: str | None
    min_quantity: float
    expires_at: date | None
    location: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class PantryOverview(BaseModel):
    total_items: int
    low_stock_items: int
    expiring_within_7_days: int


class NoteCreate(BaseModel):
    title: str
    content: str
    kind: NoteKind = NoteKind.NOTE
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    mood: int | None = Field(default=None, ge=1, le=10)


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    kind: NoteKind | None = None
    tags: list[str] | None = None
    pinned: bool | None = None
    mood: int | None = Field(default=None, ge=1, le=10)


class NoteRead(BaseModel):
    id: int
    title: str
    content: str
    kind: NoteKind
    tags: list[str]
    pinned: bool
    mood: int | None
    created_at: datetime
    updated_at: datetime


class LinearProjectRead(BaseModel):
    id: str
    name: str
    key: str | None = None
    state: str | None = None
    description: str | None = None
    url: str | None = None


class LinearIssueRead(BaseModel):
    id: str
    identifier: str | None = None
    title: str
    state: str | None = None
    priority: int | None = None
    due_date: date | None = None
    assignee_name: str | None = None
    project_id: str | None = None
    url: str | None = None


class LinearIssueCreate(BaseModel):
    title: str
    description: str | None = None
    project_id: str | None = None
    team_id: str | None = None
    priority: int | None = Field(default=None, ge=0, le=4)
    assignee_id: str | None = None
    due_date: date | None = None


class LinearSyncResult(BaseModel):
    projects: int
    issues: int
    synced_at: datetime


class SkillExecuteRequest(BaseModel):
    action: str
    input: dict = Field(default_factory=dict)


class SkillExecuteResponse(BaseModel):
    action: str
    ok: bool
    data: dict


class DashboardOverview(BaseModel):
    open_tasks: int
    overdue_tasks: int
    this_month_expense: float
    grocery_unchecked: int
    active_habits: int
    active_goals: int
    upcoming_events_7d: int
    active_subscriptions: int
    low_stock_pantry_items: int
    notes_total: int
