import pytest
from sqlmodel import Session, select

from app.models.entities import User, UserMemory, UserProfile


def test_get_and_update_profile(client, auth_headers, test_engine, owner_id):
    # 1. GET profile initializes default if none exists
    get_res = client.get("/api/v1/assistant/profile", headers=auth_headers)
    assert get_res.status_code == 200
    profile = get_res.json()
    assert profile["user_id"] == owner_id
    assert profile["ai_tone"] == "direct"

    # 2. PUT profile updates preferences
    update_payload = {
        "dietary_preferences": ["halal", "sans-arachides"],
        "fitness_goals": "Marathon de Paris en moins de 3h30",
        "lifestyle_notes": "Course à pied 4x par semaine",
        "ai_tone": "motivant et direct",
        "onboarding_completed": True,
    }
    put_res = client.put("/api/v1/assistant/profile", headers=auth_headers, json=update_payload)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["dietary_preferences"] == ["halal", "sans-arachides"]
    assert updated["fitness_goals"] == "Marathon de Paris en moins de 3h30"
    assert updated["onboarding_completed"] is True

    # 3. Verify directly in PostgreSQL
    with Session(test_engine) as session:
        db_profile = session.exec(
            select(UserProfile).where(UserProfile.user_id == owner_id)
        ).first()
        assert db_profile is not None
        assert db_profile.fitness_goals == "Marathon de Paris en moins de 3h30"


def test_memories_crud_lifecycle(client, auth_headers, test_engine, owner_id):
    # 1. Create a memory via POST
    create_payload = {
        "category": "health_fitness",
        "fact": "Genou fragile suite opération ligaments croisés",
        "confidence": 1.0,
    }
    create_res = client.post("/api/v1/assistant/memories", headers=auth_headers, json=create_payload)
    assert create_res.status_code == 201
    created = create_res.json()
    memory_id = created["id"]
    assert created["fact"] == create_payload["fact"]
    assert created["is_active"] is True

    # 2. List memories via GET
    list_res = client.get("/api/v1/assistant/memories", headers=auth_headers)
    assert list_res.status_code == 200
    memories = list_res.json()
    assert any(m["id"] == memory_id for m in memories)

    # 3. Delete memory via DELETE
    del_res = client.delete(f"/api/v1/assistant/memories/{memory_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # 4. Verify memory is omitted from active list
    list_res_after = client.get("/api/v1/assistant/memories", headers=auth_headers)
    assert list_res_after.status_code == 200
    memories_after = list_res_after.json()
    assert not any(m["id"] == memory_id for m in memories_after)

    # 5. Verify in DB that it is soft-deleted (is_active = False)
    with Session(test_engine) as session:
        db_mem = session.get(UserMemory, memory_id)
        assert db_mem is not None
        assert db_mem.is_active is False
