from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import (
    AccountType,
    EventType,
    FitnessExerciseMode,
    FitnessSessionStatus,
    FitnessSessionType,
    GoalStatus,
    HabitFrequency,
    CalendarCategory,
    CalendarSource,
    MealSlot,
    NoteKind,
    SubscriptionInterval,
    TaskPriority,
    TaskStatus,
    SupermarketStore,
    SupermarketTargetType,
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
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    priority: int = 3
    note: str | None = None


class GroceryItemUpdate(BaseModel):
    name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    checked: bool | None = None
    priority: int | None = None
    note: str | None = None


class GroceryItemRead(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    category: str | None
    image_url: str | None
    store_label: str | None
    external_id: str | None
    packaging: str | None
    price_text: str | None
    product_url: str | None
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
    store: SupermarketStore | None = None
    store_label: str | None = None
    external_id: str | None = None
    category: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    image_url: str | None = None


class RecipeIngredientRead(BaseModel):
    id: int
    recipe_id: int
    name: str
    quantity: float
    unit: str
    note: str | None
    store: SupermarketStore | None = None
    store_label: str | None = None
    external_id: str | None = None
    category: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    image_url: str | None = None


class SupermarketSearchRequest(BaseModel):
    store: SupermarketStore = SupermarketStore.INTERMARCHE
    queries: list[str] = Field(default_factory=list, min_length=1, max_length=10)
    max_results: int = Field(default=10, ge=1, le=30)
    promotions_only: bool = False


class SupermarketSearchResult(BaseModel):
    cache_id: int
    store: SupermarketStore
    query: str
    external_id: str | None
    name: str
    brand: str | None
    category: str | None = None
    packaging: str | None
    price_amount: float | None
    price_text: str | None
    image_url: str | None
    product_url: str | None
    fetched_at: datetime
    expires_at: datetime


class SupermarketStoreRead(BaseModel):
    key: SupermarketStore
    label: str
    supports_search: bool = True
    supports_mapping: bool = True
    supports_cart_automation: bool = False


class SupermarketMappingCreate(BaseModel):
    cache_id: int | None = None
    store: SupermarketStore = SupermarketStore.INTERMARCHE
    external_id: str
    store_label: str
    name_snapshot: str
    category_snapshot: str | None = None
    packaging_snapshot: str | None = None
    price_snapshot: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    last_verified_at: datetime | None = None


class SupermarketMappingRead(BaseModel):
    id: int
    target_type: SupermarketTargetType
    target_id: int
    store: SupermarketStore
    external_id: str
    store_label: str
    name_snapshot: str
    category_snapshot: str | None
    packaging_snapshot: str | None
    price_snapshot: str | None
    product_url: str | None
    image_url: str | None
    last_verified_at: datetime
    active: bool
    created_at: datetime
    updated_at: datetime


class RecipeCreate(BaseModel):
    name: str
    description: str | None = None
    instructions: str
    steps: list[str] = Field(default_factory=list)
    utensils: list[str] = Field(default_factory=list)
    prep_minutes: int = 0
    cook_minutes: int = 0
    servings: int = 1
    tags: list[str] = Field(default_factory=list)
    source_url: str | None = None
    source_platform: str | None = None
    source_title: str | None = None
    source_description: str | None = None
    source_transcript: str | None = None
    ingredients: list[RecipeIngredientIn] = Field(default_factory=list)


class RecipeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    steps: list[str] | None = None
    utensils: list[str] | None = None
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    servings: int | None = None
    tags: list[str] | None = None
    source_url: str | None = None
    source_platform: str | None = None
    source_title: str | None = None
    source_description: str | None = None
    source_transcript: str | None = None
    ingredients: list[RecipeIngredientIn] | None = None


class RecipeCookRequest(BaseModel):
    servings_override: int | None = Field(default=None, ge=1, le=100)
    note: str | None = None


class RecipeCookResult(BaseModel):
    recipe_id: int
    recipe_name: str
    cooked_at: datetime
    note: str | None = None
    missing_ingredients: list[MissingIngredientRead]
    pantry_consumption: list[MealIngredientConsumptionRead]


class RecipeRead(BaseModel):
    id: int
    name: str
    description: str | None
    instructions: str
    steps: list[str]
    utensils: list[str]
    prep_minutes: int
    cook_minutes: int
    servings: int
    tags: list[str]
    source_url: str | None
    source_platform: str | None
    source_title: str | None
    source_description: str | None
    source_transcript: str | None
    ingredients: list[RecipeIngredientRead]
    created_at: datetime
    updated_at: datetime


class VideoSourceRequest(BaseModel):
    url: str


class TranscriptSegmentRead(BaseModel):
    start: float | None = None
    duration: float | None = None
    text: str


class VideoSourceRead(BaseModel):
    url: str
    canonical_url: str | None = None
    platform: str
    title: str | None = None
    description: str | None = None
    transcript: str | None = None
    transcript_source: str | None = None
    transcript_segments: list[TranscriptSegmentRead] = Field(default_factory=list)
    author: str | None = None
    thumbnail_url: str | None = None
    published_at: datetime | None = None
    duration_seconds: int | None = None
    warnings: list[str] = Field(default_factory=list)


class MissingIngredientRead(BaseModel):
    name: str
    needed_quantity: float
    available_quantity: float
    missing_quantity: float
    unit: str
    store: SupermarketStore | None = None
    store_label: str | None = None
    external_id: str | None = None
    category: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    image_url: str | None = None


class MealPlanCreate(BaseModel):
    planned_at: datetime | None = None
    planned_for: date | None = None
    slot: MealSlot | None = None
    recipe_id: int
    servings_override: int | None = Field(default=None, ge=1, le=100)
    note: str | None = None
    auto_add_missing_ingredients: bool = True


class MealPlanUpdate(BaseModel):
    planned_at: datetime | None = None
    planned_for: date | None = None
    slot: MealSlot | None = None
    recipe_id: int | None = None
    servings_override: int | None = Field(default=None, ge=1, le=100)
    note: str | None = None
    auto_add_missing_ingredients: bool | None = None


class MealPlanRead(BaseModel):
    id: int
    planned_at: datetime
    planned_for: date | None
    slot: MealSlot | None
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


class MealCookLogCreate(BaseModel):
    recipe_id: int
    cooked_at: datetime | None = None
    servings_override: int | None = Field(default=None, ge=1, le=100)
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


class FitnessExerciseIn(BaseModel):
    name: str
    mode: FitnessExerciseMode = FitnessExerciseMode.REPS
    reps: int | None = Field(default=None, ge=1, le=1000)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    note: str | None = None

    @model_validator(mode="after")
    def validate_tracking_value(self) -> "FitnessExerciseIn":
        if self.mode == FitnessExerciseMode.REPS:
            if self.reps is None or self.duration_minutes is not None:
                raise ValueError("reps is required when mode is reps")
        if self.mode == FitnessExerciseMode.DURATION:
            if self.duration_minutes is None or self.reps is not None:
                raise ValueError("duration_minutes is required when mode is duration")
        return self


class FitnessExerciseRead(BaseModel):
    name: str
    mode: FitnessExerciseMode
    reps: int | None = None
    duration_minutes: int | None = None
    note: str | None = None


class FitnessSessionCreate(BaseModel):
    title: str
    session_type: FitnessSessionType = FitnessSessionType.MIXED
    planned_at: datetime | None = None
    duration_minutes: int = Field(default=45, ge=1, le=600)
    exercises: list[FitnessExerciseIn | str] = Field(default_factory=list)
    note: str | None = None


class FitnessSessionUpdate(BaseModel):
    title: str | None = None
    session_type: FitnessSessionType | None = None
    planned_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    exercises: list[FitnessExerciseIn | str] | None = None
    note: str | None = None
    status: FitnessSessionStatus | None = None
    actual_duration_minutes: int | None = Field(default=None, ge=1, le=600)
    effort_rating: int | None = Field(default=None, ge=1, le=10)
    calories_burned: float | None = None


class FitnessSessionComplete(BaseModel):
    note: str | None = None
    actual_duration_minutes: int | None = Field(default=None, ge=1, le=600)
    effort_rating: int | None = Field(default=None, ge=1, le=10)
    calories_burned: float | None = None


class FitnessSessionRead(BaseModel):
    id: int
    title: str
    session_type: FitnessSessionType
    planned_at: datetime
    duration_minutes: int
    exercises: list[FitnessExerciseRead]
    note: str | None
    status: FitnessSessionStatus
    completed_at: datetime | None
    actual_duration_minutes: int | None
    effort_rating: int | None
    calories_burned: float | None
    created_at: datetime
    updated_at: datetime


class FitnessMeasurementCreate(BaseModel):
    recorded_at: datetime | None = None
    body_weight_kg: float | None = Field(default=None, ge=0, le=1000)
    body_fat_pct: float | None = Field(default=None, ge=0, le=100)
    resting_hr: int | None = Field(default=None, ge=20, le=220)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    steps: int | None = Field(default=None, ge=0)
    note: str | None = None


class FitnessMeasurementUpdate(BaseModel):
    recorded_at: datetime | None = None
    body_weight_kg: float | None = Field(default=None, ge=0, le=1000)
    body_fat_pct: float | None = Field(default=None, ge=0, le=100)
    resting_hr: int | None = Field(default=None, ge=20, le=220)
    sleep_hours: float | None = Field(default=None, ge=0, le=24)
    steps: int | None = Field(default=None, ge=0)
    note: str | None = None


class FitnessMeasurementRead(BaseModel):
    id: int
    recorded_at: datetime
    body_weight_kg: float | None
    body_fat_pct: float | None
    resting_hr: int | None
    sleep_hours: float | None
    steps: int | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class FitnessStatsRead(BaseModel):
    planned_sessions: int
    upcoming_sessions: int
    completed_sessions_30d: int
    completion_rate_30d: float
    avg_duration_minutes: float | None
    latest_body_weight_kg: float | None
    body_weight_delta_30d: float | None
    latest_resting_hr: int | None
    latest_sleep_hours: float | None


class FitnessOverviewRead(BaseModel):
    stats: FitnessStatsRead
    upcoming_sessions: list[FitnessSessionRead]
    recent_sessions: list[FitnessSessionRead]
    measurements: list[FitnessMeasurementRead]


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
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    min_quantity: float = 0
    expires_at: date | None = None
    location: str | None = None
    note: str | None = None


class PantryItemUpdate(BaseModel):
    name: str | None = None
    quantity: float | None = None
    unit: str | None = None
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
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
    image_url: str | None
    store_label: str | None
    external_id: str | None
    packaging: str | None
    price_text: str | None
    product_url: str | None
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


class AccountCreate(BaseModel):
    name: str
    account_type: AccountType = AccountType.SAVINGS
    balance: float = 0.0
    currency: str = "EUR"
    institution: str | None = None
    note: str | None = None


class AccountUpdate(BaseModel):
    name: str | None = None
    account_type: AccountType | None = None
    balance: float | None = None
    currency: str | None = None
    institution: str | None = None
    note: str | None = None
    is_active: bool | None = None


class AccountRead(BaseModel):
    id: int
    name: str
    account_type: AccountType
    balance: float
    currency: str
    institution: str | None
    note: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SavingsGoalCreate(BaseModel):
    title: str
    target_amount: float
    current_amount: float = 0.0
    currency: str = "EUR"
    target_date: date | None = None
    account_id: int | None = None
    note: str | None = None


class SavingsGoalUpdate(BaseModel):
    title: str | None = None
    target_amount: float | None = None
    current_amount: float | None = None
    currency: str | None = None
    target_date: date | None = None
    account_id: int | None = None
    note: str | None = None
    completed: bool | None = None


class SavingsGoalRead(BaseModel):
    id: int
    title: str
    target_amount: float
    current_amount: float
    currency: str
    target_date: date | None
    account_id: int | None
    note: str | None
    completed: bool
    created_at: datetime
    updated_at: datetime


class PatrimoineOverview(BaseModel):
    net_worth: float
    currency: str
    accounts: list["AccountRead"]
    goals: list["SavingsGoalRead"]


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
