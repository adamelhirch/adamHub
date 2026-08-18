from fastapi import APIRouter
from sqlmodel import select

from app.api._crud import apply_updates, create, delete, get_owned_or_404, save
from app.api.deps import CurrentOrOwnerUser, SessionDep
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

router = APIRouter(prefix="/patrimony", tags=["patrimony"])


# ── Helpers ─────────────────────────────────────────────────────────────────

def _to_account_read(acc: Account) -> AccountRead:
    return AccountRead.model_validate(acc, from_attributes=True)


def _to_goal_read(goal: SavingsGoal, accounts: dict[int, Account]) -> SavingsGoalRead:
    read = SavingsGoalRead.model_validate(goal, from_attributes=True)
    # If goal is linked to an account, use the account's live balance as current_amount
    if goal.account_id and goal.account_id in accounts:
        read.current_amount = accounts[goal.account_id].balance
    return read


def _scoped_accounts_by_id(session, user_id: int) -> dict[int, Account]:
    rows = session.exec(
        select(Account).where(Account.user_id == user_id)
    ).all()
    return {acc.id: acc for acc in rows if acc.id}


# ── Overview ─────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=PatrimoineOverview)
def get_overview(session: SessionDep, user: CurrentOrOwnerUser) -> PatrimoineOverview:
    accounts = session.exec(
        select(Account)
        .where(Account.user_id == user.id, Account.is_active.is_(True))
        .order_by(Account.name.asc())
    ).all()
    goals = session.exec(
        select(SavingsGoal)
        .where(SavingsGoal.user_id == user.id)
        .order_by(SavingsGoal.target_date.asc())
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
def create_account(payload: AccountCreate, session: SessionDep, user: CurrentOrOwnerUser) -> AccountRead:
    acc = create(session, Account(**payload.model_dump(), user_id=user.id))
    return _to_account_read(acc)


@router.get("/accounts", response_model=list[AccountRead])
def list_accounts(session: SessionDep, user: CurrentOrOwnerUser, active_only: bool = True) -> list[AccountRead]:
    stmt = select(Account).where(Account.user_id == user.id).order_by(Account.name.asc())
    if active_only:
        stmt = stmt.where(Account.is_active.is_(True))
    return [_to_account_read(acc) for acc in session.exec(stmt).all()]


@router.patch("/accounts/{account_id}", response_model=AccountRead)
def update_account(account_id: int, payload: AccountUpdate, session: SessionDep, user: CurrentOrOwnerUser) -> AccountRead:
    acc = get_owned_or_404(session, Account, account_id, user_id=user.id, detail="Account not found")
    apply_updates(acc, payload.model_dump(exclude_unset=True), touch=True)
    acc = save(session, acc)
    return _to_account_read(acc)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, session: SessionDep, user: CurrentOrOwnerUser) -> None:
    acc = get_owned_or_404(session, Account, account_id, user_id=user.id, detail="Account not found")
    delete(session, acc)


# ── Savings Goals ─────────────────────────────────────────────────────────────

@router.post("/goals", response_model=SavingsGoalRead)
def create_goal(payload: SavingsGoalCreate, session: SessionDep, user: CurrentOrOwnerUser) -> SavingsGoalRead:
    goal = create(session, SavingsGoal(**payload.model_dump(), user_id=user.id))
    accounts_by_id = _scoped_accounts_by_id(session, user.id)
    return _to_goal_read(goal, accounts_by_id)


@router.get("/goals", response_model=list[SavingsGoalRead])
def list_goals(session: SessionDep, user: CurrentOrOwnerUser) -> list[SavingsGoalRead]:
    goals = session.exec(
        select(SavingsGoal)
        .where(SavingsGoal.user_id == user.id)
        .order_by(SavingsGoal.target_date.asc())
    ).all()
    accounts_by_id = _scoped_accounts_by_id(session, user.id)
    return [_to_goal_read(g, accounts_by_id) for g in goals]


@router.patch("/goals/{goal_id}", response_model=SavingsGoalRead)
def update_goal(goal_id: int, payload: SavingsGoalUpdate, session: SessionDep, user: CurrentOrOwnerUser) -> SavingsGoalRead:
    goal = get_owned_or_404(session, SavingsGoal, goal_id, user_id=user.id, detail="Goal not found")
    apply_updates(goal, payload.model_dump(exclude_unset=True), touch=True)
    goal = save(session, goal)
    accounts_by_id = _scoped_accounts_by_id(session, user.id)
    return _to_goal_read(goal, accounts_by_id)


@router.delete("/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, session: SessionDep, user: CurrentOrOwnerUser) -> None:
    goal = get_owned_or_404(session, SavingsGoal, goal_id, user_id=user.id, detail="Goal not found")
    delete(session, goal)
