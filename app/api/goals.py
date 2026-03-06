from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import Goal, GoalMilestone, GoalStatus
from app.schemas import (
    GoalCreate,
    GoalMilestoneCreate,
    GoalMilestoneRead,
    GoalMilestoneUpdate,
    GoalRead,
    GoalUpdate,
)

router = APIRouter(prefix="/goals", tags=["goals"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=GoalRead)
def create_goal(payload: GoalCreate, session: SessionDep) -> GoalRead:
    goal = Goal(**payload.model_dump())
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return GoalRead.model_validate(goal, from_attributes=True)


@router.get("", response_model=list[GoalRead])
def list_goals(
    session: SessionDep,
    status: GoalStatus | None = None,
    limit: int = Query(default=100, ge=1, le=300),
) -> list[GoalRead]:
    statement = select(Goal).order_by(Goal.created_at.desc()).limit(limit)
    if status:
        statement = statement.where(Goal.status == status)

    goals = session.exec(statement).all()
    return [GoalRead.model_validate(goal, from_attributes=True) for goal in goals]


@router.get("/{goal_id}", response_model=GoalRead)
def get_goal(goal_id: int, session: SessionDep) -> GoalRead:
    goal = session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return GoalRead.model_validate(goal, from_attributes=True)


@router.patch("/{goal_id}", response_model=GoalRead)
def update_goal(goal_id: int, payload: GoalUpdate, session: SessionDep) -> GoalRead:
    goal = session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(goal, key, value)

    goal.updated_at = datetime.now(timezone.utc)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return GoalRead.model_validate(goal, from_attributes=True)


@router.post("/{goal_id}/milestones", response_model=GoalMilestoneRead)
def create_goal_milestone(goal_id: int, payload: GoalMilestoneCreate, session: SessionDep) -> GoalMilestoneRead:
    goal = session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    milestone = GoalMilestone(goal_id=goal_id, **payload.model_dump())
    session.add(milestone)
    session.commit()
    session.refresh(milestone)
    return GoalMilestoneRead.model_validate(milestone, from_attributes=True)


@router.get("/{goal_id}/milestones", response_model=list[GoalMilestoneRead])
def list_goal_milestones(
    goal_id: int,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[GoalMilestoneRead]:
    goal = session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    milestones = session.exec(
        select(GoalMilestone)
        .where(GoalMilestone.goal_id == goal_id)
        .order_by(GoalMilestone.created_at.desc())
        .limit(limit)
    ).all()
    return [GoalMilestoneRead.model_validate(item, from_attributes=True) for item in milestones]


@router.patch("/{goal_id}/milestones/{milestone_id}", response_model=GoalMilestoneRead)
def update_goal_milestone(
    goal_id: int,
    milestone_id: int,
    payload: GoalMilestoneUpdate,
    session: SessionDep,
) -> GoalMilestoneRead:
    goal = session.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    milestone = session.get(GoalMilestone, milestone_id)
    if not milestone or milestone.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Milestone not found")

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(milestone, key, value)

    if payload.completed is True and milestone.completed_at is None:
        milestone.completed_at = datetime.now(timezone.utc)
    if payload.completed is False:
        milestone.completed_at = None

    session.add(milestone)
    session.commit()
    session.refresh(milestone)
    return GoalMilestoneRead.model_validate(milestone, from_attributes=True)
