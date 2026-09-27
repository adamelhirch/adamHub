from typing import Any
from sqlmodel import Session

from app.models.entities import User
from app.mcp.server import _informal_schema_to_json_schema
from app.services.calendar_hub import CalendarConflictError
from app.skill.actions import ACTION_CATALOG, execute_action

# Whitelist of actions exposed to the conversational assistant for safe execution
ASSISTANT_ALLOWED_ACTIONS = {
    # Tasks
    "task.create",
    "task.list",
    "task.update",
    "task.complete",
    # Groceries
    "grocery.add_item",
    "grocery.list_items",
    "grocery.check_item",
    "grocery.delete_item",
    # Pantry
    "pantry.overview",
    "pantry.add_item",
    "pantry.list_items",
    "pantry.consume_item",
    # Recipes
    "recipe.add",
    "recipe.list",
    "recipe.get",
    "recipe.update",
    "recipe.confirm_cooked",
    "recipe.unconfirm_cooked",
    "recipe.delete",
    # Meal planning
    "meal_plan.add",
    "meal_plan.list",
    "meal_plan.confirm_cooked",
    "meal_plan.unconfirm_cooked",
    "meal_plan.delete",
    # Supermarket
    "supermarket.search",
    "supermarket.get_cart",
    "supermarket.list_carts",
    "supermarket.add_cart_item",
    "supermarket.update_cart_item",
    "supermarket.remove_cart_item",
    "supermarket.clear_cart",
    "supermarket.list_stores",
    "supermarket.list_connections",
    # Fitness
    "fitness.create_session",
    "fitness.list_sessions",
    "fitness.complete_session",
    # Calendar
    "calendar.add_item",
    "calendar.check_availability",
    "calendar.list_items",
    "calendar.agenda",
}


def get_assistant_tools() -> list[dict[str, Any]]:
    """Convert allowed ACTION_CATALOG items to standard OpenAI function-calling format."""
    tools: list[dict[str, Any]] = []

    for entry in ACTION_CATALOG:
        action_name = entry.get("action")
        if action_name not in ASSISTANT_ALLOWED_ACTIONS:
            continue

        parameters = _informal_schema_to_json_schema(entry.get("input_schema", {}))
        # OpenAI tool format
        tools.append({
            "type": "function",
            "function": {
                "name": action_name.replace(".", "__"),  # OpenAI function names convention
                "description": entry.get("description", ""),
                "parameters": parameters,
            },
        })

    return tools


serialize_catalog_to_tools = get_assistant_tools


def dispatch_assistant_tool(
    function_name: str,
    arguments: dict[str, Any],
    session: Session,
    user: User,
) -> dict[str, Any]:
    """Execute an assistant tool safely scoped to the acting user."""
    action_name = function_name.replace("__", ".")
    if action_name not in ASSISTANT_ALLOWED_ACTIONS:
        raise ValueError(f"Action '{action_name}' is not authorized for assistant execution.")

    try:
        result = execute_action(action_name, arguments, session, user=user)
        return {
            "action": action_name,
            "success": True,
            "data": result,
        }
    except CalendarConflictError as exc:
        return {
            "action": action_name,
            "success": False,
            "conflict": True,
            "error": str(exc),
            "data": exc.conflict_payload,
        }
    except ValueError as exc:
        err_msg = str(exc)
        payload: dict[str, Any] = {
            "action": action_name,
            "success": False,
            "error": err_msg,
        }
        if any(w in err_msg.lower() for w in ("connection", "connexion", "401", "cookie", "magasin")):
            payload["hint"] = "Vérifiez que votre compte magasin est connecté via l'extension AdamHUB Connect ou sélectionnez un magasin."
        return payload
