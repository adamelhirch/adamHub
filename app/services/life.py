from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, func, select

from app.models import (
    Budget,
    CalendarEvent,
    EventType,
    FinanceTransaction,
    Goal,
    GoalStatus,
    GroceryItem,
    Habit,
    HabitLog,
    Note,
    PantryItem,
    Recipe,
    RecipeIngredient,
    Subscription,
    SubscriptionInterval,
    Task,
    TaskStatus,
    TransactionKind,
)
from app.schemas import DashboardOverview, FinanceMonthSummary, PantryOverview, RecipeRead, SubscriptionProjection


def month_range(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def build_month_summary(session: Session, year: int, month: int) -> FinanceMonthSummary:
    start, end = month_range(year, month)
    statement = select(FinanceTransaction).where(
        FinanceTransaction.occurred_at >= start,
        FinanceTransaction.occurred_at < end,
    )
    txs = session.exec(statement).all()

    income = sum(tx.amount for tx in txs if tx.kind == TransactionKind.INCOME)
    expense = sum(tx.amount for tx in txs if tx.kind == TransactionKind.EXPENSE)
    by_category: dict[str, float] = {}
    for tx in txs:
        if tx.kind != TransactionKind.EXPENSE:
            continue
        by_category[tx.category] = by_category.get(tx.category, 0.0) + tx.amount

    month_str = f"{year}-{month:02d}"
    budgets = session.exec(select(Budget).where(Budget.month == month_str)).all()
    budget_analytics = []
    
    for b in budgets:
        spent = by_category.get(b.category, 0.0)
        percentage = min((spent / b.monthly_limit) * 100, 999.9) if b.monthly_limit > 0 else 0
        
        status = "ok"
        if spent > b.monthly_limit:
            status = "exceeded"
        elif spent >= b.monthly_limit * b.alert_threshold:
            status = "warning"
            
        budget_analytics.append({
            "category": b.category,
            "spent": round(spent, 2),
            "limit": round(b.monthly_limit, 2),
            "remaining": round(max(b.monthly_limit - spent, 0), 2),
            "percentage_used": round(percentage, 1),
            "status": status,
        })

    return FinanceMonthSummary(
        year=year,
        month=month,
        income=round(income, 2),
        expense=round(expense, 2),
        net=round(income - expense, 2),
        expense_by_category={k: round(v, 2) for k, v in sorted(by_category.items())},
        budgets=budget_analytics,
    )


def build_recipe_read(session: Session, recipe: Recipe) -> RecipeRead:
    ingredients = session.exec(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
    ).all()

    return RecipeRead(
        id=recipe.id,
        name=recipe.name,
        description=recipe.description,
        instructions=recipe.instructions,
        steps=recipe.steps or [],
        utensils=recipe.utensils or [],
        prep_minutes=recipe.prep_minutes,
        cook_minutes=recipe.cook_minutes,
        servings=recipe.servings,
        tags=recipe.tags,
        source_url=recipe.source_url,
        source_platform=recipe.source_platform,
        source_title=recipe.source_title,
        source_description=recipe.source_description,
        source_transcript=recipe.source_transcript,
        ingredients=[
            {
                "id": ing.id,
                "recipe_id": ing.recipe_id,
                "name": ing.name,
                "quantity": ing.quantity,
                "unit": ing.unit,
                "note": ing.note,
                "store": ing.store,
                "store_label": ing.store_label,
                "external_id": ing.external_id,
                "category": ing.category,
                "packaging": ing.packaging,
                "price_text": ing.price_text,
                "product_url": ing.product_url,
                "image_url": ing.image_url,
            }
            for ing in ingredients
        ],
        created_at=recipe.created_at,
        updated_at=recipe.updated_at,
    )


def build_subscription_projection(session: Session, currency: str = "EUR") -> SubscriptionProjection:
    subscriptions = session.exec(
        select(Subscription).where(Subscription.active.is_(True), Subscription.currency == currency)
    ).all()

    monthly = 0.0
    for sub in subscriptions:
        if sub.interval == SubscriptionInterval.WEEKLY:
            monthly += sub.amount * 52 / 12
        elif sub.interval == SubscriptionInterval.MONTHLY:
            monthly += sub.amount
        elif sub.interval == SubscriptionInterval.YEARLY:
            monthly += sub.amount / 12

    yearly = monthly * 12
    return SubscriptionProjection(
        monthly_total=round(monthly, 2),
        yearly_total=round(yearly, 2),
        currency=currency,
    )


def build_pantry_overview(session: Session, days: int = 7) -> PantryOverview:
    today = date.today()
    until = today + timedelta(days=days)

    total_items = session.exec(select(func.count()).select_from(PantryItem)).one()
    low_stock_items = session.exec(
        select(func.count()).select_from(PantryItem).where(PantryItem.quantity <= PantryItem.min_quantity)
    ).one()
    expiring_soon = session.exec(
        select(func.count())
        .select_from(PantryItem)
        .where(PantryItem.expires_at.is_not(None), PantryItem.expires_at <= until)
    ).one()

    return PantryOverview(
        total_items=int(total_items or 0),
        low_stock_items=int(low_stock_items or 0),
        expiring_within_7_days=int(expiring_soon or 0),
    )


def build_dashboard_overview(session: Session) -> DashboardOverview:
    now = datetime.now(timezone.utc)
    next_week = now + timedelta(days=7)

    open_tasks = session.exec(
        select(func.count()).select_from(Task).where(Task.status != TaskStatus.DONE)
    ).one()
    overdue_tasks = session.exec(
        select(func.count())
        .select_from(Task)
        .where(Task.status != TaskStatus.DONE, Task.due_at.is_not(None), Task.due_at < now)
    ).one()
    grocery_unchecked = session.exec(
        select(func.count()).select_from(GroceryItem).where(GroceryItem.checked.is_(False))
    ).one()
    active_habits = session.exec(
        select(func.count()).select_from(Habit).where(Habit.active.is_(True))
    ).one()
    active_goals = session.exec(
        select(func.count())
        .select_from(Goal)
        .where(Goal.status.in_([GoalStatus.PLANNED, GoalStatus.ACTIVE]))
    ).one()
    upcoming_events = session.exec(
        select(func.count())
        .select_from(CalendarEvent)
        .where(CalendarEvent.start_at >= now, CalendarEvent.start_at <= next_week)
    ).one()
    active_subscriptions = session.exec(
        select(func.count()).select_from(Subscription).where(Subscription.active.is_(True))
    ).one()
    low_stock_items = session.exec(
        select(func.count()).select_from(PantryItem).where(PantryItem.quantity <= PantryItem.min_quantity)
    ).one()

    month_summary = build_month_summary(session, now.year, now.month)

    notes_total = session.exec(select(func.count()).select_from(Note)).one()

    return DashboardOverview(
        open_tasks=int(open_tasks or 0),
        overdue_tasks=int(overdue_tasks or 0),
        this_month_expense=month_summary.expense,
        grocery_unchecked=int(grocery_unchecked or 0),
        active_habits=int(active_habits or 0),
        active_goals=int(active_goals or 0),
        upcoming_events_7d=int(upcoming_events or 0),
        active_subscriptions=int(active_subscriptions or 0),
        low_stock_pantry_items=int(low_stock_items or 0),
        notes_total=int(notes_total or 0),
    )


def list_upcoming_events(session: Session, days: int = 7, event_type: EventType | None = None) -> list[CalendarEvent]:
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=days)
    statement = (
        select(CalendarEvent)
        .where(CalendarEvent.start_at >= now, CalendarEvent.start_at <= until)
        .order_by(CalendarEvent.start_at.asc())
    )
    if event_type:
        statement = statement.where(CalendarEvent.type == event_type)
    return session.exec(statement).all()


def list_upcoming_subscriptions(session: Session, days: int = 30) -> list[Subscription]:
    today = date.today()
    until = today + timedelta(days=days)
    statement = (
        select(Subscription)
        .where(Subscription.active.is_(True), Subscription.next_due_date >= today, Subscription.next_due_date <= until)
        .order_by(Subscription.next_due_date.asc())
    )
    return session.exec(statement).all()


def update_habit_streak(session: Session, habit_id: int) -> int:
    habit = session.get(Habit, habit_id)
    if not habit:
        raise ValueError("habit_id not found")

    today = datetime.now(timezone.utc).date()
    logs = session.exec(
        select(HabitLog)
        .where(HabitLog.habit_id == habit_id)
        .order_by(HabitLog.logged_at.desc())
        .limit(30)
    ).all()

    unique_days = sorted({log.logged_at.date() for log in logs}, reverse=True)
    streak = 0
    for index, day in enumerate(unique_days):
        expected = today.toordinal() - index
        if day.toordinal() == expected:
            streak += 1
        else:
            break

    habit.streak = streak
    session.add(habit)
    session.commit()
    session.refresh(habit)
    return habit.streak
