from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlmodel import Session, delete, select

from app.core.config import get_settings
from app.models import LinearIssueCache, LinearProjectCache
from app.schemas import LinearIssueCreate, LinearIssueRead, LinearProjectRead

LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearIntegrationError(RuntimeError):
    pass


def _require_token() -> str:
    settings = get_settings()
    token = settings.linear_api_token
    if not token:
        raise LinearIntegrationError("ADAMHUB_LINEAR_API_TOKEN is not configured")
    return token


def _graphql(query: str, variables: dict | None = None) -> dict:
    token = _require_token()
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = Request(
        LINEAR_API_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": token,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        text = exc.read().decode("utf-8", errors="ignore")
        raise LinearIntegrationError(f"Linear HTTP error: {exc.code} {text}") from exc
    except URLError as exc:
        raise LinearIntegrationError(f"Linear unreachable: {exc.reason}") from exc

    if payload.get("errors"):
        message = payload["errors"][0].get("message", "Unknown Linear error")
        raise LinearIntegrationError(message)

    return payload.get("data", {})


def _node_to_project(node: dict) -> LinearProjectRead:
    state = node.get("state") or {}
    return LinearProjectRead(
        id=node["id"],
        name=node.get("name", ""),
        key=node.get("key"),
        state=state.get("name"),
        description=node.get("description"),
        url=node.get("url"),
    )


def _node_to_issue(node: dict) -> LinearIssueRead:
    state = node.get("state") or {}
    assignee = node.get("assignee") or {}
    project = node.get("project") or {}

    return LinearIssueRead(
        id=node["id"],
        identifier=node.get("identifier"),
        title=node.get("title", ""),
        state=state.get("name"),
        priority=node.get("priority"),
        due_date=node.get("dueDate"),
        assignee_name=assignee.get("name"),
        project_id=project.get("id"),
        url=node.get("url"),
    )


def fetch_projects() -> list[LinearProjectRead]:
    settings = get_settings()
    if settings.linear_team_id:
        query = """
        query Projects($teamId: String!) {
          projects(filter: { team: { id: { eq: $teamId } } }, first: 100) {
            nodes {
              id
              name
              key
              description
              url
              state { name }
            }
          }
        }
        """
        variables = {"teamId": settings.linear_team_id}
    else:
        query = """
        query Projects {
          projects(first: 100) {
            nodes {
              id
              name
              key
              description
              url
              state { name }
            }
          }
        }
        """
        variables = {}
    data = _graphql(query, variables)
    nodes = (data.get("projects") or {}).get("nodes") or []
    return [_node_to_project(node) for node in nodes]


def fetch_issues(project_id: str | None = None, limit: int = 100) -> list[LinearIssueRead]:
    query = """
    query Issues($projectId: String, $first: Int!) {
      issues(filter: { project: { id: { eq: $projectId } } }, first: $first) {
        nodes {
          id
          identifier
          title
          priority
          dueDate
          url
          state { name }
          assignee { name }
          project { id }
        }
      }
    }
    """
    variables: dict = {"projectId": project_id, "first": max(1, min(limit, 250))}
    if not project_id:
        variables = {"first": max(1, min(limit, 250))}
        query = """
        query Issues($first: Int!) {
          issues(first: $first) {
            nodes {
              id
              identifier
              title
              priority
              dueDate
              url
              state { name }
              assignee { name }
              project { id }
            }
          }
        }
        """

    data = _graphql(query, variables)
    nodes = (data.get("issues") or {}).get("nodes") or []
    return [_node_to_issue(node) for node in nodes]


def create_issue(payload: LinearIssueCreate) -> LinearIssueRead:
    settings = get_settings()
    team_id = payload.team_id or settings.linear_team_id
    if not team_id:
        raise LinearIntegrationError("team_id is required (or set ADAMHUB_LINEAR_TEAM_ID)")

    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue {
          id
          identifier
          title
          priority
          dueDate
          url
          state { name }
          assignee { name }
          project { id }
        }
      }
    }
    """

    input_payload: dict = {
        "title": payload.title,
        "teamId": team_id,
    }
    if payload.description:
        input_payload["description"] = payload.description
    if payload.project_id:
        input_payload["projectId"] = payload.project_id
    if payload.priority is not None:
        input_payload["priority"] = payload.priority
    if payload.assignee_id:
        input_payload["assigneeId"] = payload.assignee_id
    if payload.due_date:
        input_payload["dueDate"] = payload.due_date.isoformat()

    data = _graphql(mutation, {"input": input_payload})
    created = (data.get("issueCreate") or {}).get("issue")
    if not created:
        raise LinearIntegrationError("issueCreate returned no issue")
    return _node_to_issue(created)


def sync_linear_cache(session: Session, project_id: str | None = None) -> tuple[int, int]:
    projects = fetch_projects()
    issues = fetch_issues(project_id=project_id, limit=200)

    session.exec(delete(LinearProjectCache))
    for project in projects:
        row = LinearProjectCache(
            linear_id=project.id,
            name=project.name,
            key=project.key,
            state=project.state,
            description=project.description,
            url=project.url,
            synced_at=datetime.now(UTC),
        )
        session.add(row)

    if not project_id:
        session.exec(delete(LinearIssueCache))
    else:
        session.exec(delete(LinearIssueCache).where(LinearIssueCache.project_linear_id == project_id))

    for issue in issues:
        row = LinearIssueCache(
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
        session.add(row)

    session.commit()
    return len(projects), len(issues)


def list_cached_projects(session: Session, limit: int = 100) -> list[LinearProjectRead]:
    rows = session.exec(
        select(LinearProjectCache).order_by(LinearProjectCache.name.asc()).limit(max(1, min(limit, 500)))
    ).all()
    return [
        LinearProjectRead(
            id=row.linear_id,
            name=row.name,
            key=row.key,
            state=row.state,
            description=row.description,
            url=row.url,
        )
        for row in rows
    ]


def list_cached_issues(session: Session, project_id: str | None = None, limit: int = 100) -> list[LinearIssueRead]:
    statement = select(LinearIssueCache).order_by(LinearIssueCache.synced_at.desc()).limit(max(1, min(limit, 500)))
    if project_id:
        statement = statement.where(LinearIssueCache.project_linear_id == project_id)

    rows = session.exec(statement).all()
    return [
        LinearIssueRead(
            id=row.linear_id,
            identifier=row.identifier,
            title=row.title,
            state=row.state,
            priority=row.priority,
            due_date=row.due_date,
            assignee_name=row.assignee_name,
            project_id=row.project_linear_id,
            url=row.url,
        )
        for row in rows
    ]
