import json
import pytest
from sqlmodel import Session, select

from app.models.entities import GroceryItem, Task, User
from app.services.assistant.tool_dispatcher import (
    ASSISTANT_ALLOWED_ACTIONS,
    dispatch_assistant_tool,
    get_assistant_tools,
)


def test_get_assistant_tools_schema():
    tools = get_assistant_tools()
    assert len(tools) > 0
    for tool in tools:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "parameters" in fn
        assert fn["parameters"].get("type") == "object"
        action_name = fn["name"].replace("__", ".")
        assert action_name in ASSISTANT_ALLOWED_ACTIONS


def test_dispatch_assistant_tool_task_create(test_engine, owner_id):
    with Session(test_engine) as session:
        user = session.get(User, owner_id)
        result = dispatch_assistant_tool(
            "task__create",
            {"title": "Courir 10km", "priority": "high"},
            session,
            user,
        )

        assert result["success"] is True
        assert result["action"] == "task.create"

        created_task = session.exec(
            select(Task).where(Task.user_id == owner_id, Task.title == "Courir 10km")
        ).first()
        assert created_task is not None
        assert created_task.priority.value == "high"


def test_dispatch_assistant_tool_grocery_add_item(test_engine, owner_id):
    with Session(test_engine) as session:
        user = session.get(User, owner_id)
        result = dispatch_assistant_tool(
            "grocery__add_item",
            {"name": "Flocons d'avoine", "quantity": 2, "unit": "paquet"},
            session,
            user,
        )

        assert result["success"] is True
        assert result["action"] == "grocery.add_item"

        grocery_item = session.exec(
            select(GroceryItem).where(
                GroceryItem.user_id == owner_id,
                GroceryItem.name == "Flocons d'avoine",
            )
        ).first()
        assert grocery_item is not None
        assert grocery_item.quantity == 2


def test_dispatch_assistant_tool_unauthorized_action(test_engine, owner_id):
    with Session(test_engine) as session:
        user = session.get(User, owner_id)
        with pytest.raises(ValueError, match="not authorized"):
            dispatch_assistant_tool(
                "supermarket__delete_connection",
                {"connection_id": 1},
                session,
                user,
            )


def test_assistant_chat_tool_execution_flow(client, auth_headers, test_engine, owner_id):
    response = client.post(
        "/api/v1/assistant/chat",
        headers=auth_headers,
        json={"message": "Ajoute la tâche Méditation matinale"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    content = response.text
    assert "event: tool_call" in content
    assert "event: tool_result" in content
    assert "task.create" in content
    assert "event: done" in content

    # Verify task persisted in PostgreSQL
    with Session(test_engine) as session:
        task = session.exec(
            select(Task).where(Task.user_id == owner_id, Task.title.contains("Méditation"))
        ).first()
        assert task is not None
