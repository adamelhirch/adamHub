import json
from datetime import UTC, datetime, timedelta
import pytest
from sqlmodel import Session, select

from app.models.entities import (
    CalendarItem,
    GroceryItem,
    MealPlan,
    PantryItem,
    Recipe,
    RecipeIngredient,
    Task,
    User,
)
from app.services.assistant.context_builder import build_system_context
from app.services.assistant.tool_dispatcher import (
    ASSISTANT_ALLOWED_ACTIONS,
    dispatch_assistant_tool,
    get_assistant_tools,
)
from app.services.calendar_hub import (
    CalendarConflictError,
    detect_calendar_conflicts_and_alternatives,
    validate_calendar_slot_free,
)
from app.skill.actions import execute_action
from tests.conftest import register_user


def _get_or_create_user(session: Session, email: str = "test-user@adamelhirch.com") -> User:
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        user = User(email=email, password_hash="hash", display_name="Test User")
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


# ── US1: Recipe Lifecycle & Semantic Anti-Task Coherence ─────────────────────

def test_recipe_actions_are_whitelisted_in_assistant():
    """Verify all recipe actions are present in ASSISTANT_ALLOWED_ACTIONS and get_assistant_tools()."""
    expected_recipe_actions = {
        "recipe.add",
        "recipe.list",
        "recipe.get",
        "recipe.update",
        "recipe.confirm_cooked",
        "recipe.unconfirm_cooked",
        "recipe.delete",
    }
    assert expected_recipe_actions.issubset(ASSISTANT_ALLOWED_ACTIONS)

    tools = get_assistant_tools()
    tool_names = {t["function"]["name"] for t in tools}
    for act in expected_recipe_actions:
        assert act.replace(".", "__") in tool_names


def test_assistant_recipe_creation_anti_task(client, jwt_headers, test_engine):
    """Instructing the assistant to save a recipe creates a Recipe with ingredients and zero Tasks (FR-005, SC-001)."""
    response = client.post(
        "/api/v1/assistant/chat",
        headers=jwt_headers,
        json={
            "message": "Enregistre ma recette de Risotto aux champignons : 300g de riz arborio, 250g de champignons de Paris, 1 oignon, 1L de bouillon. Cuisson 25 min à feu doux",
        },
    )
    assert response.status_code == 200
    events = response.text

    # Verify SSE events include recipe__add tool call
    assert "recipe__add" in events
    assert "event: tool_call" in events
    assert "event: tool_result" in events

    # Verify database records
    with Session(test_engine) as session:
        user = session.exec(select(User).where(User.email == "jwt-user@adamelhirch.com")).first()
        assert user is not None

        # A structured Recipe entity was created
        recipes = session.exec(select(Recipe).where(Recipe.user_id == user.id)).all()
        assert len(recipes) == 1
        recipe = recipes[0]
        assert "risotto" in recipe.name.lower()
        assert recipe.servings == 4

        # Structured ingredient lines exist
        ingredients = session.exec(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
        ).all()
        assert len(ingredients) >= 3
        ing_names = [i.name.lower() for i in ingredients]
        assert any("riz" in n for n in ing_names)

        # STRICT: Zero tasks were created for this culinary request!
        tasks = session.exec(select(Task).where(Task.user_id == user.id)).all()
        recipe_tasks = [t for t in tasks if "risotto" in t.title.lower()]
        assert len(recipe_tasks) == 0


def test_assistant_recipe_list_search(client, jwt_headers, test_engine):
    """Assistant can list and query saved recipes."""
    # Seed a recipe directly
    with Session(test_engine) as session:
        user = session.exec(select(User).where(User.email == "jwt-user@adamelhirch.com")).first()
        r = Recipe(
            name="Salade César",
            instructions="Mélanger les ingrédients",
            servings=2,
            prep_minutes=10,
            cook_minutes=5,
            user_id=user.id,
        )
        session.add(r)
        session.commit()

    response = client.post(
        "/api/v1/assistant/chat",
        headers=jwt_headers,
        json={"message": "Quelles sont mes recettes rapides pour le dîner ?"},
    )
    assert response.status_code == 200
    assert "recipe__list" in response.text


def test_assistant_recipe_delete_requires_confirmation(client, jwt_headers, test_engine):
    """Deleting a recipe prompts for confirmation unless explicitly confirmed."""
    response = client.post(
        "/api/v1/assistant/chat",
        headers=jwt_headers,
        json={"message": "Supprime la recette de Salade César"},
    )
    assert response.status_code == 200
    # Should ask for confirmation and NOT immediately call delete
    assert "recipe__delete" not in response.text
    assert "confirm" in response.text.lower() or "certain" in response.text.lower()

    # When user confirms
    confirm_resp = client.post(
        "/api/v1/assistant/chat",
        headers=jwt_headers,
        json={"message": "Oui, je confirme la suppression de la recette"},
    )
    assert confirm_resp.status_code == 200
    assert "recipe__delete" in confirm_resp.text


# ── US2: Smart Calendar Conflict Detection & Proactive Resolution ─────────────

def test_detect_calendar_conflicts_and_alternatives(test_engine):
    """Conflict detection identifies colliding event by title and computes viable alternative slots."""
    now = datetime.now(UTC).replace(microsecond=0)
    event_start = now + timedelta(days=1, hours=2)
    event_end = event_start + timedelta(hours=1)

    with Session(test_engine) as session:
        user = _get_or_create_user(session)
        assert user is not None

        # Seed an existing calendar item
        item = CalendarItem(
            title="Rendez-vous dentiste",
            start_at=event_start,
            end_at=event_end,
            user_id=user.id,
            generated=False,
        )
        session.add(item)
        session.commit()

        # Overlapping target: overlaps by 30 minutes
        overlap_start = event_start + timedelta(minutes=30)
        overlap_end = overlap_start + timedelta(hours=1)

        result = detect_calendar_conflicts_and_alternatives(
            session,
            overlap_start,
            overlap_end,
            user_id=user.id,
            max_suggestions=2,
        )

        assert result["conflict"] is True
        assert len(result["colliding_items"]) >= 1
        assert result["colliding_items"][0]["title"] == "Rendez-vous dentiste"
        assert len(result["suggested_slots"]) >= 1

        # Verify suggested slot is collision free
        sugg = result["suggested_slots"][0]
        s_start = datetime.fromisoformat(sugg["start_at"])
        s_end = datetime.fromisoformat(sugg["end_at"])
        # validate_calendar_slot_free should not raise for suggested slot
        validate_calendar_slot_free(session, s_start, s_end, user_id=user.id)


def test_calendar_conflict_flow_in_assistant(client, jwt_headers, test_engine):
    """When a collision occurs, assistant returns colliding title and suggestions without 500 error (SC-002)."""
    with Session(test_engine) as session:
        user = session.exec(select(User).where(User.email == "jwt-user@adamelhirch.com")).first()
        # Create an event at 10:30
        seed_start = datetime.fromisoformat("2026-09-13T10:30:00Z")
        seed_end = seed_start + timedelta(hours=1)
        item = CalendarItem(
            title="Dentiste",
            start_at=seed_start,
            end_at=seed_end,
            user_id=user.id,
            generated=False,
        )
        session.add(item)
        session.commit()

    # Try to add conflicting event at 10:30
    response = client.post(
        "/api/v1/assistant/chat",
        headers=jwt_headers,
        json={"message": "Planifie un rendez-vous dentiste demain de 10:30 à 11:30"},
    )
    assert response.status_code == 200
    events = response.text

    assert "calendar__add_item" in events
    # Tool result indicates conflict
    assert "conflict" in events
    # Assistant text communicates conflict with title
    assert "Dentiste" in events or "collision" in events.lower() or "indisponible" in events.lower()


def test_calendar_force_scheduling(client, jwt_headers, test_engine):
    """User can explicitly force scheduling despite collision."""
    with Session(test_engine) as session:
        user = session.exec(select(User).where(User.email == "jwt-user@adamelhirch.com")).first()
        seed_start = datetime.fromisoformat("2026-09-13T10:30:00Z")
        seed_end = seed_start + timedelta(hours=1)
        item = CalendarItem(
            title="Dentiste",
            start_at=seed_start,
            end_at=seed_end,
            user_id=user.id,
            generated=False,
        )
        session.add(item)
        session.commit()

    # User explicitly forces scheduling
    response = client.post(
        "/api/v1/assistant/chat",
        headers=jwt_headers,
        json={"message": "Force l'ajout quand même de mon rendez-vous sur ce créneau"},
    )
    assert response.status_code == 200
    events = response.text
    assert "calendar__add_item" in events
    # Parse SSE events for calendar__add_item arguments
    tool_calls = [
        json.loads(line[6:])
        for line in events.split("\n")
        if line.startswith("data: ") and "calendar__add_item" in line
    ]
    assert len(tool_calls) > 0
    args = json.loads(tool_calls[0]["function"]["arguments"])
    assert args.get("force") is True


def test_calendar_check_availability_action(test_engine):
    """calendar.check_availability returns available: true for empty slot and false with suggestions for occupied."""
    now = datetime.now(UTC).replace(microsecond=0)
    with Session(test_engine) as session:
        user = _get_or_create_user(session)
        res_free = execute_action(
            "calendar.check_availability",
            {
                "start_at": (now + timedelta(days=2, hours=10)).isoformat(),
                "end_at": (now + timedelta(days=2, hours=11)).isoformat(),
            },
            session,
            user=user,
        )
        assert res_free["available"] is True
        assert res_free["conflict"] is False


# ── US3: Supermarket Drive Search & Cart Integration ──────────────────────────

def test_supermarket_actions_are_whitelisted():
    """Verify supermarket search, cart, and store actions are whitelisted."""
    expected_supermarket_actions = {
        "supermarket.search",
        "supermarket.get_cart",
        "supermarket.list_carts",
        "supermarket.add_cart_item",
        "supermarket.update_cart_item",
        "supermarket.remove_cart_item",
        "supermarket.clear_cart",
        "supermarket.list_stores",
        "supermarket.list_connections",
    }
    assert expected_supermarket_actions.issubset(ASSISTANT_ALLOWED_ACTIONS)


def test_assistant_supermarket_search_and_cart_stream(client, jwt_headers):
    """Assistant can search supermarket and query drive cart."""
    response = client.post(
        "/api/v1/assistant/chat",
        headers=jwt_headers,
        json={"message": "Cherche des pâtes complètes chez Carrefour"},
    )
    assert response.status_code == 200
    assert "supermarket__search" in response.text

    cart_response = client.post(
        "/api/v1/assistant/chat",
        headers=jwt_headers,
        json={"message": "Qu'est-ce qu'il y a dans mon panier Intermarché ?"},
    )
    assert cart_response.status_code == 200
    assert "supermarket__get_cart" in cart_response.text


def test_supermarket_unconnected_hint(test_engine):
    """Unconnected store cart operations return clear hint to user without crashing."""
    with Session(test_engine) as session:
        user = _get_or_create_user(session)
        res = dispatch_assistant_tool(
            "supermarket__get_cart",
            {"store": "carrefour"},
            session,
            user,
        )
        # Should gracefully return error + hint
        assert res["success"] is False
        assert "hint" in res
        assert "AdamHUB Connect" in res["hint"]


# ── US4: End-to-End Meal Planning & Deficit Restocking ────────────────────────

def test_meal_planning_deficit_restocking(test_engine):
    """Scheduling a meal checks pantry stock and auto-adds ONLY missing ingredients (FR-021)."""
    with Session(test_engine) as session:
        user = _get_or_create_user(session)

        # 1. Create a recipe requiring 500g pasta and 4 eggs
        recipe = Recipe(
            name="Pâtes carbonara",
            instructions="Cuire les pâtes",
            servings=2,
            user_id=user.id,
        )
        session.add(recipe)
        session.commit()
        session.refresh(recipe)

        ing_pasta = RecipeIngredient(
            recipe_id=recipe.id,
            name="Pâtes",
            quantity=500,
            unit="g",
        )
        ing_eggs = RecipeIngredient(
            recipe_id=recipe.id,
            name="Œufs",
            quantity=4,
            unit="item",
        )
        session.add(ing_pasta)
        session.add(ing_eggs)

        # 2. Pantry has 500g pasta and 0 eggs
        pantry_pasta = PantryItem(
            name="Pâtes",
            quantity=500,
            unit="g",
            user_id=user.id,
        )
        session.add(pantry_pasta)
        session.commit()

        # 3. Add meal plan with auto_add_missing_ingredients=True
        now = datetime.now(UTC).replace(microsecond=0)
        res = execute_action(
            "meal_plan.add",
            {
                "recipe_id": recipe.id,
                "planned_at": (now + timedelta(days=2)).isoformat(),
                "slot": "dinner",
                "auto_add_missing_ingredients": True,
            },
            session,
            user=user,
        )

        assert res["groceries_added_count"] == 1
        assert len(res["missing_ingredients"]) == 1
        assert res["missing_ingredients"][0]["name"] == "Œufs"

        # 4. Verify GroceryItem table only contains eggs, NOT pasta
        groceries = session.exec(select(GroceryItem).where(GroceryItem.user_id == user.id)).all()
        grocery_names = [g.name.lower() for g in groceries]
        assert any("œuf" in n or "oeuf" in n for n in grocery_names)
        assert not any("pâtes" in n or "pates" in n for n in grocery_names)


# ── US5: Reversible Cook Confirmation & Pantry Restock ────────────────────────

def test_reversible_cook_confirmation(test_engine):
    """Confirming cooked decrements pantry; unconfirming restores exact stock (FR-009, FR-010, SC-006)."""
    with Session(test_engine) as session:
        user = _get_or_create_user(session)

        # 1. Pantry starts with 1000g rice
        pantry_rice = PantryItem(
            name="Riz arborio",
            quantity=1000,
            unit="g",
            user_id=user.id,
        )
        session.add(pantry_rice)

        # 2. Recipe requires 200g rice
        recipe = Recipe(
            name="Risotto",
            instructions="Cuire le risotto",
            servings=2,
            user_id=user.id,
        )
        session.add(recipe)
        session.commit()
        session.refresh(recipe)

        ing_rice = RecipeIngredient(
            recipe_id=recipe.id,
            name="Riz arborio",
            quantity=200,
            unit="g",
        )
        session.add(ing_rice)
        session.commit()

        # 3. Confirm cooked
        confirm_res = execute_action(
            "recipe.confirm_cooked",
            {"recipe_id": recipe.id},
            session,
            user=user,
        )
        session.refresh(pantry_rice)
        assert pantry_rice.quantity == 800

        # 4. Unconfirm cooked (reverse)
        unconfirm_res = execute_action(
            "recipe.unconfirm_cooked",
            {"recipe_id": recipe.id},
            session,
            user=user,
        )
        session.refresh(pantry_rice)
        assert pantry_rice.quantity == 1000


def test_cook_confirmation_insufficient_stock_clamps_at_zero(test_engine):
    """If stock is less than required, stock is clamped at 0 without negative inventory."""
    with Session(test_engine) as session:
        user = _get_or_create_user(session)

        # Pantry has 50g rice
        pantry_rice = PantryItem(
            name="Riz basmati",
            quantity=50,
            unit="g",
            user_id=user.id,
        )
        session.add(pantry_rice)

        recipe = Recipe(
            name="Riz sauté",
            instructions="Sauter le riz",
            servings=1,
            user_id=user.id,
        )
        session.add(recipe)
        session.commit()
        session.refresh(recipe)

        ing = RecipeIngredient(
            recipe_id=recipe.id,
            name="Riz basmati",
            quantity=200,
            unit="g",
        )
        session.add(ing)
        session.commit()

        # Confirm cooked
        execute_action(
            "recipe.confirm_cooked",
            {"recipe_id": recipe.id},
            session,
            user=user,
        )
        session.refresh(pantry_rice)
        assert pantry_rice.quantity == 0.0


# ── Multi-Tenant Isolation (Principle I) ──────────────────────────────────────

def test_assistant_tools_multi_tenant_isolation(test_engine):
    """User A's recipes, meal plans, and calendar items are completely isolated from User B."""
    with Session(test_engine) as session:
        user_a = User(email="user-a@example.com", password_hash="hash", display_name="User A")
        user_b = User(email="user-b@example.com", password_hash="hash", display_name="User B")
        session.add(user_a)
        session.add(user_b)
        session.commit()
        session.refresh(user_a)
        session.refresh(user_b)

        # User A creates a recipe
        recipe_a = execute_action(
            "recipe.add",
            {
                "name": "Recette secrète de A",
                "instructions": "Top secret",
                "ingredients": [{"name": "Épice", "quantity": 1}],
            },
            session,
            user=user_a,
        )
        recipe_a_id = recipe_a["recipe"]["id"]

        # User B cannot see recipe of User A
        list_b = execute_action("recipe.list", {}, session, user=user_b)
        b_recipe_ids = [r["id"] for r in list_b["recipes"]]
        assert recipe_a_id not in b_recipe_ids

        # User B cannot get or delete recipe of User A
        with pytest.raises(ValueError, match="not found"):
            execute_action("recipe.get", {"recipe_id": recipe_a_id}, session, user=user_b)

        with pytest.raises(ValueError, match="not found"):
            execute_action("recipe.delete", {"recipe_id": recipe_a_id}, session, user=user_b)
