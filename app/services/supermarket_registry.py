from __future__ import annotations

from dataclasses import dataclass

from app.models import SupermarketStore


@dataclass(frozen=True, slots=True)
class SupermarketStoreDefinition:
    key: SupermarketStore
    label: str
    supports_search: bool = True
    supports_mapping: bool = True
    supports_cart_automation: bool = False
    scraper_name: str | None = None
    notes: str | None = None


STORE_REGISTRY: tuple[SupermarketStoreDefinition, ...] = (
    SupermarketStoreDefinition(
        key=SupermarketStore.INTERMARCHE,
        label="Intermarché",
        scraper_name="intermarche",
        notes="Live HTML scraping with optional Camoufox fallback.",
    ),
    SupermarketStoreDefinition(
        key=SupermarketStore.UBEREATS,
        label="Uber Eats",
        scraper_name="ubereats",
        supports_mapping=False,
        supports_cart_automation=True,
        notes=(
            "Internal JSON API scraping. Requires data/cookies_ubereats.json and "
            "a selected store (POST /supermarket/ubereats/selected-store)."
        ),
    ),
    SupermarketStoreDefinition(
        key=SupermarketStore.CARREFOUR,
        label="Carrefour",
        scraper_name="carrefour",
        supports_mapping=False,
        notes=(
            "Carrefour Drive search via /api/marketing/search. Requires "
            "data/cookies_carrefour.json from a logged-in browser session "
            "with a Drive store selected (prices are store-specific)."
        ),
    ),
)


def list_store_definitions() -> list[SupermarketStoreDefinition]:
    return list(STORE_REGISTRY)


def get_store_definition(store: SupermarketStore) -> SupermarketStoreDefinition | None:
    for definition in STORE_REGISTRY:
        if definition.key == store:
            return definition
    return None


def supports_store(store: SupermarketStore) -> bool:
    return get_store_definition(store) is not None
