from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep
from app.core.security import require_api_key
from app.models import LinearIssueCache
from app.schemas import LinearIssueCreate, LinearIssueRead, LinearProjectRead, LinearSyncResult
from app.services.linear_hub import (
    LinearIntegrationError,
    create_issue,
    fetch_issues,
    fetch_projects,
    list_cached_issues,
    list_cached_projects,
    sync_linear_cache,
)

router = APIRouter(prefix="/linear", tags=["linear"], dependencies=[Depends(require_api_key)])


@router.get("/projects", response_model=list[LinearProjectRead])
def list_linear_projects(
    session: SessionDep,
    source: str = Query(default="cache", pattern="^(cache|live)$"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[LinearProjectRead]:
    if source == "cache":
        return list_cached_projects(session, limit=limit)

    try:
        return fetch_projects()[:limit]
    except LinearIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/issues", response_model=list[LinearIssueRead])
def list_linear_issues(
    session: SessionDep,
    project_id: str | None = None,
    source: str = Query(default="cache", pattern="^(cache|live)$"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[LinearIssueRead]:
    if source == "cache":
        return list_cached_issues(session, project_id=project_id, limit=limit)

    try:
        return fetch_issues(project_id=project_id, limit=limit)
    except LinearIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/issues", response_model=LinearIssueRead)
def create_linear_issue(payload: LinearIssueCreate, session: SessionDep) -> LinearIssueRead:
    try:
        issue = create_issue(payload)
    except LinearIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    cache_row = LinearIssueCache(
        linear_id=issue.id,
        identifier=issue.identifier,
        title=issue.title,
        state=issue.state,
        priority=issue.priority,
        due_date=issue.due_date,
        assignee_name=issue.assignee_name,
        project_linear_id=issue.project_id,
        url=issue.url,
        synced_at=datetime.now(UTC),
    )
    session.add(cache_row)
    session.commit()
    return issue


@router.post("/sync", response_model=LinearSyncResult)
def sync_linear(session: SessionDep, project_id: str | None = None) -> LinearSyncResult:
    try:
        projects, issues = sync_linear_cache(session, project_id=project_id)
    except LinearIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return LinearSyncResult(projects=projects, issues=issues, synced_at=datetime.now(UTC))
