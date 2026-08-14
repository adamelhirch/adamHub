from __future__ import annotations

from pydantic import BaseModel


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
