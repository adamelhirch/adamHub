"""MCP server for AdamHUB — exposes the skill action catalog as MCP tools.

Tools are generated from ``ACTION_CATALOG`` (``app/skill/actions.py``), the
same registry ``POST /api/v1/skill/execute`` dispatches through — there is no
separate hand-maintained tool list to drift out of sync (the failure mode
that made ``adamhub-assistant/SKILL.md`` go stale).

Auth resolves a bearer token to a ``User`` the same way
``resolve_current_or_owner_user`` does for the HTTP API (JWT, then a per-user
API key, then the shared Owner key). A non-Owner caller can list and call the
tenant-scoped domain prefixes: the 5 MVP domains plus the domains opened to
SaaS users during the multi-tenant pivot (tasks, finances, calendar, habits,
goals, events, fitness, subscriptions, patrimony, notes, video). Only
``dashboard.overview`` remains owner-only — see
``docs/adr/0001-owner-only-off-mvp-domains.md``. Everything else is rejected
even if invoked directly by name, not merely hidden from the tool listing (a
client is never trusted to only call what it was shown).
"""

from __future__ import annotations

import json
import secrets
from typing import Any

import mcp_types as types
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel import Server
from sqlmodel import Session
from starlette.applications import Starlette

from app.core.auth import decode_token, resolve_user_by_api_key
from app.core.config import get_settings
from app.core.db import engine
from app.models import User
from app.skill.actions import ACTION_CATALOG, execute_action

# The 16 tenant-scoped domain prefixes — the actions a non-Owner (per-user
# API key) caller may list or execute: the 5 MVP domains plus the 11 domains
# opened to SaaS users during the multi-tenant pivot. Only `dashboard`
# (dashboard.overview) stays owner-only, matching the remaining router-level
# gates in app/api/router.py's includes.
MVP_ACTION_PREFIXES = {
    "grocery", "recipe", "pantry", "meal_plan", "supermarket",
    "task", "finance", "calendar", "habit", "goal", "event",
    "fitness", "subscription", "patrimony", "note", "video",
}

_ACTION_BY_NAME = {entry["action"]: entry for entry in ACTION_CATALOG}


def _is_owner(user: User) -> bool:
    owner_email = (get_settings().owner_email or "").strip().lower()
    return bool(owner_email) and user.email.strip().lower() == owner_email


def _action_allowed(action: str, user: User) -> bool:
    if _is_owner(user):
        return True
    return action.split(".", 1)[0] in MVP_ACTION_PREFIXES


def _informal_schema_to_json_schema(input_schema: dict[str, str]) -> dict[str, Any]:
    """Best-effort JSON Schema from ACTION_CATALOG's informal notation.

    e.g. ``{"quantity": "float?", "store": "a|b?", "tags": "string[]?"}``.
    Real validation still happens server-side in each handler (pydantic
    models, explicit checks) — this only drives client-side tool-call
    affordances (autocomplete, required-field hints), not correctness.
    """
    type_map = {"int": "integer", "float": "number", "bool": "boolean"}
    properties: dict[str, Any] = {}
    required: list[str] = []
    for field, spec in input_schema.items():
        optional = spec.endswith("?")
        body = spec[:-1] if optional else spec
        is_array = body.endswith("[]")
        base = body[:-2] if is_array else body
        if "|" in base:
            item_schema: dict[str, Any] = {"type": "string", "enum": base.split("|")}
        elif base in ("string", "int", "float", "bool", "object"):
            item_schema = {"type": type_map.get(base, base)}
        else:
            # Nested/free-form shapes (e.g. "[{name, quantity, ...}]") — the
            # action's own description documents the exact shape in prose.
            item_schema = {"type": "object"}
        properties[field] = {"type": "array", "items": item_schema} if is_array else item_schema
        if not optional:
            required.append(field)
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def resolve_user_for_bearer_token(session: Session, token: str) -> User | None:
    """Same resolution order as resolve_current_or_owner_user, for a bare token string.

    MCP's Bearer auth hands the server only the raw token (no header/Request
    object to reuse resolve_current_or_owner_user directly), so this mirrors
    it: JWT -> per-user API key -> shared Owner key.
    """
    try:
        payload = decode_token(token)
        user = session.get(User, int(payload.get("sub")))
        if user is not None and user.is_active:
            return user
    except Exception:
        pass

    user = resolve_user_by_api_key(session, token)
    if user is not None:
        return user

    settings = get_settings()
    if any(secrets.compare_digest(token, key) for key in settings.api_keys_list):
        owner_email = (settings.owner_email or "").strip().lower()
        if owner_email:
            from sqlmodel import select

            return session.exec(select(User).where(User.email == owner_email)).first()

    return None


class _ApiKeyTokenVerifier:
    """Plugs AdamHUB's existing auth resolution into MCP's Bearer-auth hook.

    A short-lived session is opened per verification (this runs outside the
    FastAPI dependency-injection system) — matches how background jobs and
    scripts elsewhere in the app open a session against the shared engine.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        with Session(engine) as session:
            user = resolve_user_for_bearer_token(session, token)
        if user is None:
            return None
        return AccessToken(token=token, client_id="adamhub-mcp", scopes=["mcp"], subject=str(user.id))


def _current_user(session: Session) -> User:
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        raise ValueError("Unauthenticated")
    user = session.get(User, int(access_token.subject))
    if user is None or not user.is_active:
        raise ValueError("Unauthenticated")
    return user


async def _on_list_tools(ctx: Any, params: types.PaginatedRequestParams | None) -> types.ListToolsResult:
    with Session(engine) as session:
        user = _current_user(session)
        tools = [
            types.Tool(
                name=entry["action"],
                description=entry["description"],
                input_schema=_informal_schema_to_json_schema(entry["input_schema"]),
            )
            for entry in ACTION_CATALOG
            if _action_allowed(entry["action"], user)
        ]
    return types.ListToolsResult(tools=tools)


async def _on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
    with Session(engine) as session:
        user = _current_user(session)
        if not _action_allowed(params.name, user):
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Action not available: {params.name}")],
                is_error=True,
            )
        if params.name not in _ACTION_BY_NAME:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Unknown action: {params.name}")],
                is_error=True,
            )
        try:
            result = execute_action(params.name, dict(params.arguments or {}), session, user=user)
        except (ValueError, TypeError, KeyError) as exc:
            return types.CallToolResult(content=[types.TextContent(type="text", text=str(exc))], is_error=True)

    return types.CallToolResult(content=[types.TextContent(type="text", text=json.dumps(result, default=str))])


mcp_server = Server(
    "adamhub",
    version="1.0.0",
    instructions=(
        "AdamHUB's task/finance/grocery/recipe/etc. life-management surface. "
        "Non-Owner API keys reach all tenant-scoped domains: groceries, "
        "pantry, recipes, meal plans, supermarket/cart, tasks, finances, "
        "calendar, habits, goals, events, fitness, subscriptions, patrimony, "
        "notes, and video. Only dashboard.overview stays owner-only."
    ),
    on_list_tools=_on_list_tools,
    on_call_tool=_on_call_tool,
)
"""Module-level singleton so app/main.py's lifespan can drive the same
instance's session_manager (required — the streamable-HTTP session manager
needs an active task group for the whole process lifetime, entered via
`async with mcp_server.session_manager.run(): ...`) that build_mcp_app()
mounts. Built once at import time, before the app's lifespan ever runs."""


def build_mcp_app() -> Starlette:
    """Build the mountable MCP ASGI app (mounted at /mcp by app/main.py)."""
    settings = get_settings()
    # issuer_url/resource_server_url are required by AuthSettings for the RFC
    # 9728 protected-resource-metadata route, even though there is no real
    # OAuth authorization server behind this yet (auth_server_provider is not
    # set, so no token/registration endpoints are exposed) — a bearer token is
    # verified directly by _ApiKeyTokenVerifier. Phase 2 (OAuth) replaces this
    # with the app actually acting as the issuer.
    base_url = settings.public_base_url
    return mcp_server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        auth=AuthSettings(issuer_url=base_url, resource_server_url=base_url),
        token_verifier=_ApiKeyTokenVerifier(),
    )
