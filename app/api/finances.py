from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import Budget, FinanceTransaction, TransactionKind
from app.schemas import (
    BudgetCreate,
    BudgetRead,
    FinanceMonthSummary,
    FinanceTransactionCreate,
    FinanceTransactionRead,
)
from app.services.life import build_month_summary

router = APIRouter(prefix="/finances", tags=["finances"], dependencies=[Depends(require_api_key)])


@router.post("/transactions", response_model=FinanceTransactionRead)
def create_transaction(payload: FinanceTransactionCreate, session: SessionDep) -> FinanceTransactionRead:
    tx = FinanceTransaction(**payload.model_dump())
    if tx.occurred_at is None:
        tx.occurred_at = datetime.now(timezone.utc)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return FinanceTransactionRead.model_validate(tx, from_attributes=True)


@router.get("/transactions", response_model=list[FinanceTransactionRead])
def list_transactions(
    session: SessionDep,
    kind: TransactionKind | None = None,
    year: int | None = Query(default=None, ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    limit: int = Query(default=100, ge=1, le=300),
) -> list[FinanceTransactionRead]:
    statement = select(FinanceTransaction).order_by(FinanceTransaction.occurred_at.desc()).limit(limit)
    if kind:
        statement = statement.where(FinanceTransaction.kind == kind)
    if year and month:
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        statement = statement.where(
            FinanceTransaction.occurred_at >= start,
            FinanceTransaction.occurred_at < end,
        )

    txs = session.exec(statement).all()
    return [FinanceTransactionRead.model_validate(tx, from_attributes=True) for tx in txs]


@router.post("/budgets", response_model=BudgetRead)
def create_budget(payload: BudgetCreate, session: SessionDep) -> BudgetRead:
    if len(payload.month) != 7 or payload.month[4] != "-":
        raise HTTPException(status_code=400, detail="month must be in format YYYY-MM")

    budget = Budget(**payload.model_dump())
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return BudgetRead.model_validate(budget, from_attributes=True)


@router.get("/budgets", response_model=list[BudgetRead])
def list_budgets(session: SessionDep, month: str | None = None) -> list[BudgetRead]:
    statement = select(Budget).order_by(Budget.month.desc(), Budget.category.asc())
    if month:
        statement = statement.where(Budget.month == month)

    budgets = session.exec(statement).all()
    return [BudgetRead.model_validate(item, from_attributes=True) for item in budgets]


@router.get("/summary", response_model=FinanceMonthSummary)
def month_summary(
    session: SessionDep,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> FinanceMonthSummary:
    return build_month_summary(session, year, month)


@router.get("/analytics", response_model=FinanceMonthSummary)
def month_analytics_compat(
    session: SessionDep,
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
) -> FinanceMonthSummary:
    """Compatibility alias for older frontend clients."""
    return build_month_summary(session, year, month)
