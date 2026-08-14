from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models import (
    AccountType,
    SubscriptionInterval,
    TransactionKind,
)


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
