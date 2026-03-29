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
        notes="Only active store in v1. Add new stores here when their scraper and mappings are ready.",
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
