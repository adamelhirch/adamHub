from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import Account, SavingsGoal
from app.schemas import (
    AccountCreate,
    AccountRead,
    AccountUpdate,
    PatrimoineOverview,
    SavingsGoalCreate,
    SavingsGoalRead,
    SavingsGoalUpdate,
)

router = APIRouter(
    prefix="/patrimony",
    tags=["patrimony"],
    dependencies=[Depends(require_api_key)],
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _to_account_read(acc: Account) -> AccountRead:
    return AccountRead.model_validate(acc, from_attributes=True)


def _to_goal_read(goal: SavingsGoal, accounts: dict[int, Account]) -> SavingsGoalRead:
    read = SavingsGoalRead.model_validate(goal, from_attributes=True)
    # If goal is linked to an account, use the account's live balance as current_amount
    if goal.account_id and goal.account_id in accounts:
        read.current_amount = accounts[goal.account_id].balance
    return read


# ── Overview ─────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=PatrimoineOverview)
def get_overview(session: SessionDep) -> PatrimoineOverview:
    accounts = session.exec(
        select(Account).where(Account.is_active.is_(True)).order_by(Account.name.asc())
    ).all()
    goals = session.exec(
        select(SavingsGoal).order_by(SavingsGoal.target_date.asc())
    ).all()

    accounts_by_id = {acc.id: acc for acc in accounts if acc.id}
    net_worth = sum(acc.balance for acc in accounts)

    return PatrimoineOverview(
        net_worth=net_worth,
        currency="EUR",
        accounts=[_to_account_read(acc) for acc in accounts],
        goals=[_to_goal_read(g, accounts_by_id) for g in goals],
    )


# ── Accounts ─────────────────────────────────────────────────────────────────

@router.post("/accounts", response_model=AccountRead)
def create_account(payload: AccountCreate, session: SessionDep) -> AccountRead:
    acc = Account(**payload.model_dump())
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return _to_account_read(acc)


@router.get("/accounts", response_model=list[AccountRead])
def list_accounts(session: SessionDep, active_only: bool = True) -> list[AccountRead]:
    stmt = select(Account).order_by(Account.name.asc())
    if active_only:
        stmt = stmt.where(Account.is_active.is_(True))
    return [_to_account_read(acc) for acc in session.exec(stmt).all()]


@router.patch("/accounts/{account_id}", response_model=AccountRead)
def update_account(account_id: int, payload: AccountUpdate, session: SessionDep) -> AccountRead:
    acc = session.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(acc, key, value)
    acc.updated_at = datetime.now(timezone.utc)
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return _to_account_read(acc)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, session: SessionDep) -> None:
    acc = session.get(Account, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    session.delete(acc)
    session.commit()


# ── Savings Goals ─────────────────────────────────────────────────────────────

@router.post("/goals", response_model=SavingsGoalRead)
def create_goal(payload: SavingsGoalCreate, session: SessionDep) -> SavingsGoalRead:
    goal = SavingsGoal(**payload.model_dump())
    session.add(goal)
    session.commit()
    session.refresh(goal)
    accounts_by_id = {acc.id: acc for acc in session.exec(select(Account)).all() if acc.id}
    return _to_goal_read(goal, accounts_by_id)


@router.get("/goals", response_model=list[SavingsGoalRead])
def list_goals(session: SessionDep) -> list[SavingsGoalRead]:
    goals = session.exec(select(SavingsGoal).order_by(SavingsGoal.target_date.asc())).all()
    accounts_by_id = {acc.id: acc for acc in session.exec(select(Account)).all() if acc.id}
    return [_to_goal_read(g, accounts_by_id) for g in goals]


@router.patch("/goals/{goal_id}", response_model=SavingsGoalRead)
def update_goal(goal_id: int, payload: SavingsGoalUpdate, session: SessionDep) -> SavingsGoalRead:
    goal = session.get(SavingsGoal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, key, value)
    goal.updated_at = datetime.now(timezone.utc)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    accounts_by_id = {acc.id: acc for acc in session.exec(select(Account)).all() if acc.id}
    return _to_goal_read(goal, accounts_by_id)


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, session: SessionDep) -> None:
    goal = session.get(SavingsGoal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    session.delete(goal)
    session.commit()
