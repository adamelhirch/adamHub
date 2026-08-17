"""MCP tool listing/execution scoping — the ADR-0001 boundary applied to MCP.

app/mcp/server.py builds tools from ACTION_CATALOG (app/skill/actions.py) and
opens its own DB sessions against app.mcp.server.engine (outside FastAPI's
request-scoped DI, matching the scheduler's existing pattern) — each test
monkeypatches that module attribute to the isolated test_engine so nothing
here touches the real dev database.
"""

import asyncio

import mcp_types as types
import pytest
from sqlmodel import Session

from app.mcp import server as mcp_server
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from tests.conftest import OWNER_EMAIL, register_user


def _run(coro):
    return asyncio.run(coro)


def _auth_as(user_id: int):
    """Context manager-less auth_context_var set/reset around one MCP call."""
    token = auth_context_var.set(
        AuthenticatedUser(AccessToken(token="t", client_id="test", scopes=["mcp"], subject=str(user_id)))
    )
    return token


def _tool_names(result: types.ListToolsResult) -> set[str]:
    return {tool.name for tool in result.tools}


@pytest.fixture()
def owner_user_id(client, test_engine) -> int:
    from sqlmodel import select

    from app.models import User

    with Session(test_engine) as session:
        return session.exec(select(User).where(User.email == OWNER_EMAIL)).first().id


def test_owner_sees_full_catalog(client, test_engine, owner_user_id, monkeypatch):
    monkeypatch.setattr(mcp_server, "engine", test_engine)
    token = _auth_as(owner_user_id)
    try:
        result = _run(mcp_server._on_list_tools(None, None))
    finally:
        auth_context_var.reset(token)

    names = _tool_names(result)
    assert "grocery.add_item" in names
    assert "task.create" in names
    assert "finance.add_transaction" in names
    assert len(names) == len(mcp_server.ACTION_CATALOG)


def test_non_owner_sees_only_mvp_tools(client, test_engine, monkeypatch):
    saas = register_user(client, "mcp-saas-user@adamelhirch.com")
    monkeypatch.setattr(mcp_server, "engine", test_engine)
    token = _auth_as(int(saas["user"]["id"]))
    try:
        result = _run(mcp_server._on_list_tools(None, None))
    finally:
        auth_context_var.reset(token)

    names = _tool_names(result)
    assert "grocery.add_item" in names
    assert "supermarket.search" in names
    assert "task.create" not in names
    assert "finance.add_transaction" not in names
    assert names <= {
        name for name in mcp_server._ACTION_BY_NAME if name.split(".", 1)[0] in mcp_server.MVP_ACTION_PREFIXES
    }


def test_non_owner_call_of_owner_only_action_is_rejected_even_though_hidden(client, test_engine, monkeypatch):
    """Defense in depth: rejected on direct invocation, not just absent from listing."""
    saas = register_user(client, "mcp-saas-direct-call@adamelhirch.com")
    monkeypatch.setattr(mcp_server, "engine", test_engine)
    token = _auth_as(int(saas["user"]["id"]))
    try:
        result = _run(
            mcp_server._on_call_tool(
                None, types.CallToolRequestParams(name="task.create", arguments={"title": "leak attempt"})
            )
        )
    finally:
        auth_context_var.reset(token)

    assert result.is_error is True
    assert "not available" in result.content[0].text.lower()


def test_non_owner_can_execute_mvp_action(client, test_engine, monkeypatch):
    saas = register_user(client, "mcp-saas-execute@adamelhirch.com")
    monkeypatch.setattr(mcp_server, "engine", test_engine)
    token = _auth_as(int(saas["user"]["id"]))
    try:
        result = _run(
            mcp_server._on_call_tool(
                None, types.CallToolRequestParams(name="grocery.add_item", arguments={"name": "Pommes"})
            )
        )
    finally:
        auth_context_var.reset(token)

    assert result.is_error is not True
    assert "Pommes" in result.content[0].text


def test_owner_can_execute_owner_only_action(client, test_engine, owner_user_id, monkeypatch):
    monkeypatch.setattr(mcp_server, "engine", test_engine)
    token = _auth_as(owner_user_id)
    try:
        result = _run(
            mcp_server._on_call_tool(
                None,
                types.CallToolRequestParams(
                    name="task.create", arguments={"title": "MCP owner smoke test"}
                ),
            )
        )
    finally:
        auth_context_var.reset(token)

    assert result.is_error is not True


def test_informal_schema_conversion():
    schema = mcp_server._informal_schema_to_json_schema(
        {
            "name": "string",
            "quantity": "float?",
            "store": "intermarche|carrefour?",
            "tags": "string[]?",
        }
    )
    assert schema["properties"]["name"] == {"type": "string"}
    assert schema["properties"]["quantity"] == {"type": "number"}
    assert schema["properties"]["store"] == {"type": "string", "enum": ["intermarche", "carrefour"]}
    assert schema["properties"]["tags"] == {"type": "array", "items": {"type": "string"}}
    assert schema["required"] == ["name"]
