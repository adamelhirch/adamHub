import json
import pytest
from sqlmodel import Session

from app.models.entities import (
    GroceryItem,
    PantryItem,
    UserMemory,
    UserProfile,
)
from app.services.assistant.context_builder import build_system_context


def test_context_builder_includes_profile_and_memories(test_engine, owner_id):
    with Session(test_engine) as session:
        # Seed profile
        profile = UserProfile(
            user_id=owner_id,
            dietary_preferences=["sans-gluten", "végétarien"],
            fitness_goals="Prise de masse 4x par semaine",
            lifestyle_notes="Écoute du rap et de la drill",
            ai_tone="motivant et direct",
        )
        session.add(profile)

        # Seed memory
        memory = UserMemory(
            user_id=owner_id,
            category="health_fitness",
            fact="Blessure épaule droite : pas de développé couché",
            is_active=True,
        )
        session.add(memory)

        # Seed grocery item
        grocery = GroceryItem(
            user_id=owner_id,
            name="Acheter des protéines",
            checked=False,
        )
        session.add(grocery)

        # Seed low pantry stock
        pantry = PantryItem(
            user_id=owner_id,
            name="Œufs bio",
            quantity=1,
            unit="boîte",
        )
        session.add(pantry)
        session.commit()

        context = build_system_context(session, owner_id)
        assert "sans-gluten, végétarien" in context
        assert "Prise de masse 4x par semaine" in context
        assert "Blessure épaule droite" in context
        assert "Acheter des protéines" in context
        assert "Œufs bio" in context
        assert "motivant et direct" in context


def test_assistant_chat_streaming_endpoint(client, auth_headers):
    response = client.post(
        "/api/v1/assistant/chat",
        headers=auth_headers,
        json={"message": "Que dois-je cuisiner aujourd'hui ?"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    content = response.text
    assert "event: delta" in content
    assert "event: done" in content


def test_assistant_chat_unauthorized_fails(client):
    response = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Hello"},
    )
    assert response.status_code == 401
