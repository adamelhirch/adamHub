import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from app.core.config import get_settings


from app.services.assistant.tool_dispatcher import (
    get_assistant_tools,
    serialize_catalog_to_tools,
)


async def stream_openrouter_chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream chat completions from OpenRouter via SSE.

    Yields dictionaries with keys:
    - 'delta': str (text fragment)
    - 'tool_calls': list[dict] (accumulated or delta tool calls)
    - 'finish_reason': str | None
    """
    settings = get_settings()
    api_key = (settings.openrouter_api_key or "").strip()
    target_model = model or settings.ai_model

    # In dev/test environments without an OpenRouter key, provide a deterministic stream
    if not api_key:
        if messages and messages[-1].get("role") == "tool":
            tool_content = messages[-1].get("content", "")
            try:
                t_json = json.loads(tool_content)
                data = t_json.get("data") or {}
                if data.get("conflict"):
                    colliding = data.get("colliding_items", [])
                    suggs = data.get("suggested_slots", [])
                    coll_title = colliding[0]["title"] if colliding else "un événement existant"
                    alt_strs = [s.get("label", s.get("start_at", "")) for s in suggs[:2]]
                    alt_desc = " ou ".join(alt_strs) if alt_strs else "aucun autre créneau libre"
                    yield {
                        "delta": f"Créneau indisponible : collision détectée avec '{coll_title}'. Je te suggère : {alt_desc}. Veux-tu un de ces créneaux ou forcer l'ajout ?",
                        "tool_calls": [],
                        "finish_reason": "stop",
                    }
                    return
                elif "meal_plan" in data:
                    added_count = data.get("groceries_added_count", 0)
                    missing = data.get("missing_ingredients", [])
                    miss_names = ", ".join([m.get("name", "") for m in missing[:3]])
                    msg = "Repas planifié avec succès !"
                    if added_count > 0:
                        msg += f" {added_count} ingrédient(s) manquant(s) ajouté(s) à la liste de courses ({miss_names})."
                    yield {"delta": msg, "tool_calls": [], "finish_reason": "stop"}
                    return
                elif "recipe" in data or "pantry_restore" in data or "pantry_consumption" in data:
                    yield {"delta": "Action culinaire effectuée avec succès !", "tool_calls": [], "finish_reason": "stop"}
                    return
                elif "cart" in data or "carts" in data or "items" in data:
                    yield {"delta": "Opération supermarché drive effectuée avec succès !", "tool_calls": [], "finish_reason": "stop"}
                    return
            except Exception:
                pass

            yield {"delta": "Toutes les étapes ont été traitées avec succès.", "tool_calls": [], "finish_reason": "stop"}
            return

        user_text = ""
        has_image = False
        for m in reversed(messages):
            if m.get("role") == "user":
                raw_content = m.get("content", "")
                if isinstance(raw_content, list):
                    text_parts = [
                        p.get("text", "")
                        for p in raw_content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    has_image = any(
                        isinstance(p, dict) and p.get("type") == "image_url"
                        for p in raw_content
                    )
                    user_text = " ".join(text_parts)
                else:
                    user_text = str(raw_content)
                break

        user_lower = user_text.lower()

        # 1. RECIPES: strictly evaluated before tasks to prevent task misfiling (FR-005, SC-001)
        if ("recette" in user_lower or "risotto" in user_lower or "salade césar" in user_lower or "salade cesar" in user_lower or "curry" in user_lower or "carbonara" in user_lower) and tools:
            # Delete recipe confirmation check
            if any(w in user_lower for w in ("suppr", "effac")):
                if any(w in user_lower for w in ("confirme", "oui", "sûr", "sur")):
                    yield {
                        "delta": "Je supprime la recette demandée. ",
                        "tool_calls": [{
                            "id": "call_mock_recipe_delete",
                            "type": "function",
                            "function": {
                                "name": "recipe__delete",
                                "arguments": json.dumps({"recipe_id": 1}),
                            },
                        }],
                        "finish_reason": "tool_calls",
                    }
                    return
                else:
                    yield {
                        "delta": "Êtes-vous certain de vouloir supprimer cette recette ? Cette action est irréversible. Confirmez pour procéder.",
                        "tool_calls": [],
                        "finish_reason": "stop",
                    }
                    return

            # Recipe list / search
            if any(w in user_lower for w in ("quelles", "liste", "cherche", "trouve", "rapide", "mes recettes")):
                yield {
                    "delta": "Voici vos recettes correspondantes : ",
                    "tool_calls": [{
                        "id": "call_mock_recipe_list",
                        "type": "function",
                        "function": {
                            "name": "recipe__list",
                            "arguments": json.dumps({"query": "rapide" if "rapide" in user_lower else ""}),
                        },
                    }],
                    "finish_reason": "tool_calls",
                }
                return

            # Recipe add/create
            if "risotto" in user_lower:
                r_name = "Risotto aux champignons"
                r_servings = 4
                r_ings = [
                    {"name": "Riz arborio", "quantity": 300, "unit": "g"},
                    {"name": "Champignons de Paris", "quantity": 250, "unit": "g"},
                    {"name": "Oignon", "quantity": 1, "unit": "item"},
                    {"name": "Bouillon", "quantity": 1, "unit": "L"},
                ]
                r_instructions = "Cuisson 25 min à feu doux"
            elif "césar" in user_lower or "cesar" in user_lower:
                r_name = "Salade César"
                r_servings = 2
                r_ings = [
                    {"name": "Poulet", "quantity": 200, "unit": "g"},
                    {"name": "Romaine", "quantity": 1, "unit": "item"},
                    {"name": "Parmesan", "quantity": 30, "unit": "g"},
                ]
                r_instructions = "Mélanger le poulet cuit, la romaine et le parmesan."
            elif "carbonara" in user_lower:
                r_name = "Pâtes carbonara"
                r_servings = 2
                r_ings = [
                    {"name": "Pâtes", "quantity": 500, "unit": "g"},
                    {"name": "Œufs", "quantity": 4, "unit": "item"},
                    {"name": "Guanciale", "quantity": 150, "unit": "g"},
                    {"name": "Pecorino", "quantity": 50, "unit": "g"},
                ]
                r_instructions = "Cuire les pâtes et mélanger avec les œufs et le pecorino."
            else:
                r_name = "Recette maison"
                r_servings = 2
                r_ings = [{"name": "Ingrédient", "quantity": 1, "unit": "item"}]
                r_instructions = user_text

            yield {
                "delta": f"J'enregistre votre recette '{r_name}' avec ses ingrédients structurés. ",
                "tool_calls": [{
                    "id": "call_mock_recipe_add",
                    "type": "function",
                    "function": {
                        "name": "recipe__add",
                        "arguments": json.dumps({
                            "name": r_name,
                            "instructions": r_instructions,
                            "servings": r_servings,
                            "ingredients": r_ings,
                        }),
                    },
                }],
                "finish_reason": "tool_calls",
            }
            return

        # 2. CALENDAR SCHEDULING & CONFLICT (FR-016 - FR-020)
        if any(w in user_lower for w in ("planifie", "rendez-vous", "séance de sport", "dentiste", "calendrier", "agenda")) and ("repas" not in user_lower and "dîner" not in user_lower and "carbonara" not in user_lower) and tools:
            force = any(w in user_lower for w in ("force", "quand même", "malgré"))
            title = "Rendez-vous"
            if "dentiste" in user_lower:
                title = "Dentiste"
            elif "sport" in user_lower or "séance" in user_lower:
                title = "Séance de sport"

            # Parse or mock time slot
            start_at = "2026-09-13T10:30:00Z"
            end_at = "2026-09-13T11:30:00Z"
            if "14" in user_lower or "15" in user_lower:
                start_at = "2026-09-13T14:30:00Z"
                end_at = "2026-09-13T15:30:00Z"

            yield {
                "delta": f"Je vérifie le créneau et planifie '{title}'. ",
                "tool_calls": [{
                    "id": "call_mock_calendar_add",
                    "type": "function",
                    "function": {
                        "name": "calendar__add_item",
                        "arguments": json.dumps({
                            "title": title,
                            "start_at": start_at,
                            "end_at": end_at,
                            "force": force,
                        }),
                    },
                }],
                "finish_reason": "tool_calls",
            }
            return

        # 3. SUPERMARKET DRIVE (FR-011 - FR-015)
        if any(w in user_lower for w in ("intermarché", "intermarche", "carrefour", "leclerc", "auchan", "drive")) and tools:
            store = "intermarche"
            for st in ["carrefour", "leclerc", "auchan", "intermarche"]:
                if st in user_lower:
                    store = st
                    break

            if any(w in user_lower for w in ("cherche", "recherche", "trouve", "pâtes", "lait")):
                query = "lait bio" if "lait" in user_lower else "pâtes complètes"
                yield {
                    "delta": f"Je recherche {query} chez {store.capitalize()}. ",
                    "tool_calls": [{
                        "id": "call_mock_supermarket_search",
                        "type": "function",
                        "function": {
                            "name": "supermarket__search",
                            "arguments": json.dumps({"store": store, "queries": [query]}),
                        },
                    }],
                    "finish_reason": "tool_calls",
                }
                return

            if "panier" in user_lower:
                if any(w in user_lower for w in ("ajoute", "mets")):
                    yield {
                        "delta": f"J'ajoute ce produit à votre panier {store.capitalize()}. ",
                        "tool_calls": [{
                            "id": "call_mock_supermarket_cart_add",
                            "type": "function",
                            "function": {
                                "name": "supermarket__add_cart_item",
                                "arguments": json.dumps({"store": store, "cache_id": 1, "quantity": 2}),
                            },
                        }],
                        "finish_reason": "tool_calls",
                    }
                    return
                else:
                    yield {
                        "delta": f"Voici le contenu de votre panier {store.capitalize()} : ",
                        "tool_calls": [{
                            "id": "call_mock_supermarket_cart_get",
                            "type": "function",
                            "function": {
                                "name": "supermarket__get_cart",
                                "arguments": json.dumps({"store": store}),
                            },
                        }],
                        "finish_reason": "tool_calls",
                    }
                    return

        # 4. MEAL PLANNING & PANTRY DEFICIT (FR-021, US4)
        if any(w in user_lower for w in ("planifie", "dîner", "diner", "repas")) and any(w in user_lower for w in ("jeudi", "vendredi", "soir", "midi", "curry", "carbonara", "repas")) and tools:
            yield {
                "delta": "Je planifie ce repas et vérifie les ingrédients en stock dans votre garde-manger. ",
                "tool_calls": [{
                    "id": "call_mock_meal_plan_add",
                    "type": "function",
                    "function": {
                        "name": "meal_plan__add",
                        "arguments": json.dumps({
                            "recipe_id": 1,
                            "planned_at": "2026-09-17T19:00:00Z",
                            "slot": "dinner",
                            "auto_add_missing_ingredients": True,
                        }),
                    },
                }],
                "finish_reason": "tool_calls",
            }
            return

        # 5. REVERSIBLE COOK CONFIRMATION (FR-009, FR-010, US5)
        if ("cuisiné" in user_lower or "cuisson" in user_lower) and tools:
            if any(w in user_lower for w in ("annule", "trompé", "trompe", "erreur", "undo")):
                yield {
                    "delta": "J'annule la confirmation de cuisson et restaure les quantités dans votre garde-manger. ",
                    "tool_calls": [{
                        "id": "call_mock_cook_unconfirm",
                        "type": "function",
                        "function": {
                            "name": "recipe__unconfirm_cooked",
                            "arguments": json.dumps({"recipe_id": 1}),
                        },
                    }],
                    "finish_reason": "tool_calls",
                }
                return
            else:
                yield {
                    "delta": "Je confirme la cuisson et décrémente les stocks d'ingrédients du garde-manger. ",
                    "tool_calls": [{
                        "id": "call_mock_cook_confirm",
                        "type": "function",
                        "function": {
                            "name": "recipe__confirm_cooked",
                            "arguments": json.dumps({"recipe_id": 1}),
                        },
                    }],
                    "finish_reason": "tool_calls",
                }
                return

        # 6. TASKS (Fallback for non-recipe tasks)
        if ("tâche" in user_lower or "task" in user_lower) and tools:
            title = user_text
            for prefix in ["ajoute la tâche", "ajoute une tâche", "crée la tâche", "crée une tâche", "nouvelle tâche", "tâche"]:
                if prefix in user_lower:
                    idx = user_lower.find(prefix) + len(prefix)
                    title = user_text[idx:].strip(" :-\"'\t\r\n") or "Nouvelle tâche"
                    break
            yield {
                "delta": "J'ajoute cette tâche pour toi. ",
                "tool_calls": [{
                    "id": "call_mock_task",
                    "type": "function",
                    "function": {
                        "name": "task__create",
                        "arguments": json.dumps({"title": title, "priority": "medium"}),
                    },
                }],
                "finish_reason": "tool_calls",
            }
            yield {"delta": f"\nC'est fait ! La tâche '{title}' a été créée.", "tool_calls": [], "finish_reason": "stop"}
            return

        # 7. GROCERIES
        if ("courses" in user_lower or "achète" in user_lower) and tools:
            item_name = "Articles demandés"
            for candidate in ["œufs", "oeufs", "lait", "pain", "poulet", "pommes"]:
                if candidate in user_lower:
                    item_name = candidate.capitalize()
                    break
            yield {
                "delta": f"J'ajoute {item_name} à ta liste de courses. ",
                "tool_calls": [{
                    "id": "call_mock_grocery",
                    "type": "function",
                    "function": {
                        "name": "grocery__add_item",
                        "arguments": json.dumps({"name": item_name, "quantity": 1}),
                    },
                }],
                "finish_reason": "tool_calls",
            }
            yield {"delta": f"\n{item_name} a bien été ajouté à ta liste de courses.", "tool_calls": [], "finish_reason": "stop"}
            return

        yield {"delta": "Bonjour ! Je suis l'assistant AdamHUB Copilot. ", "tool_calls": [], "finish_reason": None}
        yield {"delta": "Ton contexte et tes préférences ont bien été pris en compte. ", "tool_calls": [], "finish_reason": None}
        yield {"delta": "Que puis-je faire pour toi aujourd'hui ?", "tool_calls": [], "finish_reason": "stop"}
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": settings.public_base_url,
        "X-Title": "AdamHUB Copilot",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": target_model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            f"{settings.openrouter_base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                yield {
                    "delta": f"[Erreur OpenRouter {response.status_code}]: {error_text.decode('utf-8', errors='replace')}",
                    "tool_calls": [],
                    "finish_reason": "error",
                }
                return

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choice = chunk.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    content = delta.get("content", "")
                    tool_calls = delta.get("tool_calls", [])
                    finish_reason = choice.get("finish_reason")

                    yield {
                        "delta": content or "",
                        "tool_calls": tool_calls or [],
                        "finish_reason": finish_reason,
                    }
                except json.JSONDecodeError:
                    continue
