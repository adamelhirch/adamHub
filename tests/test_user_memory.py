import pytest
from sqlmodel import Session, select

from app.models.entities import UserMemory
from app.services.assistant.memory_extractor import (
    consolidate_and_save_memory,
    extract_facts_heuristic,
)


def test_extract_facts_heuristic():
    # Test health constraint
    facts = extract_facts_heuristic("J'ai une blessure à l'épaule droite depuis hier")
    assert len(facts) >= 1
    assert facts[0]["category"] == "health_fitness"
    assert "épaule droite" in facts[0]["fact"].lower()

    # Test nutrition restriction
    facts = extract_facts_heuristic("Je suis intolérant au lactose et végétarien")
    assert len(facts) >= 1
    assert facts[0]["category"] == "nutrition"

    # Test lifestyle
    facts = extract_facts_heuristic("J'écoute principalement du rap US pendant mes séances")
    assert len(facts) >= 1
    assert facts[0]["category"] == "lifestyle"

    # Test ephemeral task ignored
    facts = extract_facts_heuristic("Ajoute 2 packs de lait et du pain pour demain matin")
    assert len(facts) == 0


def test_consolidate_and_save_memory(test_engine, owner_id):
    with Session(test_engine) as session:
        # 1. Initial memory save
        mem1 = consolidate_and_save_memory(
            session=session,
            user_id=owner_id,
            category="health_fitness",
            fact="Blessure à l'épaule droite : pas de développé couché",
            confidence=0.95,
        )
        assert mem1 is not None
        assert mem1.is_active is True

        # 2. De-duplication: saving the identical fact returns existing
        mem_dup = consolidate_and_save_memory(
            session=session,
            user_id=owner_id,
            category="health_fitness",
            fact="Blessure à l'épaule droite : pas de développé couché",
        )
        assert mem_dup.id == mem1.id

        # 3. Contradiction / Evolution resolution:
        # An updated condition on the same subject deactivates the older one
        mem2 = consolidate_and_save_memory(
            session=session,
            user_id=owner_id,
            category="health_fitness",
            fact="Épaule droite guérie : reprise de la musculation progressive",
            confidence=0.98,
        )
        assert mem2.id != mem1.id
        assert mem2.is_active is True

        # Refresh mem1
        session.refresh(mem1)
        assert mem1.is_active is False

        # Verify active memories query only returns mem2
        active = session.exec(
            select(UserMemory).where(
                UserMemory.user_id == owner_id,
                UserMemory.is_active == True,  # noqa: E712
            )
        ).all()
        assert len(active) == 1
        assert active[0].id == mem2.id


def test_memory_api_tenancy_isolation(client, auth_headers, test_engine, owner_id):
    with Session(test_engine) as session:
        # Create memory for owner
        mem = UserMemory(
            user_id=owner_id,
            category="preferences",
            fact="Préfère les réponses sous forme de puces courtes",
            is_active=True,
        )
        session.add(mem)
        session.commit()

    # Owner can view memory
    resp = client.get("/api/v1/assistant/memories", headers=auth_headers)
    assert resp.status_code == 200
    memories = resp.json()
    assert any(m["fact"] == "Préfère les réponses sous forme de puces courtes" for m in memories)

    # Unauthenticated user receives 401
    unauth_resp = client.get("/api/v1/assistant/memories")
    assert unauth_resp.status_code == 401
