import json
import logging
import re
from datetime import datetime, timezone
from typing import Any
import httpx
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.db import engine
from app.models.entities import UserMemory

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """Tu es un extracteur de mémoire pour un assistant personnel IA (AdamHUB Copilot).
Ta mission : analyser l'échange entre l'utilisateur et l'assistant pour détecter UNIQUEMENT les faits DURABLES et PERTINENTS sur l'utilisateur à retenir pour les sessions futures.

Catégories autorisées :
- health_fitness : blessures, limitations physiques, objectifs athlétiques, sports
- nutrition : allergies, intolérances, régimes, aversions ou préférences culinaires
- lifestyle : habitudes de travail, rythme de vie, loisirs, musique
- preferences : style de communication, organisation personnelle

Règles impératives :
1. Ignore les requêtes ponctuelles ou éphémères ("ajoute du lait aux courses", "quel temps fait-il ?").
2. N'extrais que des informations personnelles durables formulées par l'utilisateur.
3. Réponds UNIQUEMENT sous forme d'un tableau JSON d'objets, ou [] si aucun fait durable n'est présent.

Format JSON attendu :
[
  {
    "category": "health_fitness",
    "fact": "Blessure à l'épaule droite : éviter le développé couché",
    "confidence": 0.95
  }
]
"""

HEURISTIC_PATTERNS = [
    (
        r"(blessure|tendinite|entorse|douleur|déchirure|fracture|mal au|mal à l')\s+([^\.\n]+)",
        "health_fitness",
        "Contrainte physique / blessure : ",
    ),
    (
        r"(allergique|intolérant|intolérance|ne mange pas de|ne mange plus de|sans gluten|végétarien|végan)\s*([^\.\n]*)",
        "nutrition",
        "Régime / restriction alimentaire : ",
    ),
    (
        r"(j'écoute principalement|j'adore écouter|passionné par|télétravail le|je travaille chez)\s+([^\.\n]+)",
        "lifestyle",
        "Style de vie : ",
    ),
]


def extract_facts_heuristic(text: str) -> list[dict[str, Any]]:
    """Fast deterministic heuristic extraction for testing and local dev fallback."""
    results = []
    text_lower = text.lower()

    for pattern, category, prefix in HEURISTIC_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            matched_text = match.group(0).strip()
            # Clean up punctuation
            clean_fact = f"{prefix}{matched_text.capitalize()}"
            results.append({
                "category": category,
                "fact": clean_fact,
                "confidence": 0.9,
            })
    return results


async def extract_memories_from_text(
    user_message: str,
    assistant_response: str = "",
) -> list[dict[str, Any]]:
    """Extract durable personal facts using OpenRouter with heuristic fallback."""
    settings = get_settings()
    api_key = (settings.openrouter_api_key or "").strip()

    # If no OpenRouter key or in testing, use deterministic heuristics
    if not api_key:
        return extract_facts_heuristic(user_message)

    prompt = f"Message utilisateur :\n{user_message}\n\nRéponse assistant :\n{assistant_response}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": settings.public_base_url,
        "X-Title": "AdamHUB Memory Extractor",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.memory_extractor_model,
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_content = data["choices"][0]["message"]["content"].strip()
                # Parse json array
                # Strip any markdown code fences if present
                if raw_content.startswith("```"):
                    raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content)
                    raw_content = re.sub(r"\s*```$", "", raw_content)
                parsed = json.loads(raw_content)
                if isinstance(parsed, list):
                    return parsed
    except Exception as exc:
        logger.warning("OpenRouter memory extraction failed, falling back to heuristics: %s", exc)

    return extract_facts_heuristic(user_message)


def consolidate_and_save_memory(
    session: Session,
    user_id: int,
    category: str,
    fact: str,
    confidence: float = 1.0,
    source: str = "conversation",
) -> UserMemory | None:
    """Save an extracted memory and resolve conflicts/contradictions."""
    now = datetime.now(timezone.utc)
    clean_fact = fact.strip()
    if not clean_fact:
        return None

    # Check for identical active memory
    existing_same = session.exec(
        select(UserMemory).where(
            UserMemory.user_id == user_id,
            UserMemory.is_active == True,  # noqa: E712
            UserMemory.fact == clean_fact,
        )
    ).first()
    if existing_same:
        # Already remembered
        return existing_same

    # Contradiction / update resolution:
    # If an existing memory in the same category shares key nouns or topics, deactivate it.
    existing_memories = session.exec(
        select(UserMemory).where(
            UserMemory.user_id == user_id,
            UserMemory.category == category,
            UserMemory.is_active == True,  # noqa: E712
        )
    ).all()

    fact_words = set(re.findall(r"\w{4,}", clean_fact.lower()))
    for old_mem in existing_memories:
        old_words = set(re.findall(r"\w{4,}", old_mem.fact.lower()))
        # Check significant overlap in topic keywords (e.g. both mention "épaule" or "lactose")
        overlap = fact_words.intersection(old_words)
        if len(overlap) >= 2 or (len(overlap) == 1 and any(k in overlap for k in ["épaule", "genou", "dos", "lactose", "gluten", "arachide", "musculation"])):
            old_mem.is_active = False
            old_mem.updated_at = now
            session.add(old_mem)

    new_memory = UserMemory(
        user_id=user_id,
        category=category,
        fact=clean_fact,
        confidence=confidence,
        source=source,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(new_memory)
    session.commit()
    session.refresh(new_memory)
    return new_memory


async def background_memory_extractor_task(
    user_id: int,
    user_message: str,
    assistant_response: str = "",
) -> None:
    """FastAPI BackgroundTask worker for asynchronous memory extraction."""
    extracted = await extract_memories_from_text(user_message, assistant_response)
    if not extracted:
        return

    with Session(engine) as session:
        for item in extracted:
            cat = item.get("category", "lifestyle")
            fact = item.get("fact", "")
            conf = float(item.get("confidence", 1.0))
            if fact:
                consolidate_and_save_memory(
                    session=session,
                    user_id=user_id,
                    category=cat,
                    fact=fact,
                    confidence=conf,
                    source="conversation",
                )
