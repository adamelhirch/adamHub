from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    PantryItem,
    RecipeIngredient,
    SupermarketMapping,
    SupermarketSearchCache,
    SupermarketStore,
    SupermarketTargetType,
)
from app.schemas import SupermarketMappingCreate
from app.services.supermarket_registry import get_store_definition


def _validate_target_exists(session: Session, target_type: SupermarketTargetType, target_id: int) -> None:
    if target_type is SupermarketTargetType.RECIPE_INGREDIENT:
        row = session.get(RecipeIngredient, target_id)
    elif target_type is SupermarketTargetType.PANTRY_ITEM:
        row = session.get(PantryItem, target_id)
    else:
        row = None
    if row is None:
        raise HTTPException(status_code=404, detail=f"{target_type.value} not found")


def get_active_mapping(
    session: Session,
    target_type: SupermarketTargetType,
    target_id: int,
    store: SupermarketStore | None = None,
) -> SupermarketMapping | None:
    statement = select(SupermarketMapping).where(
        SupermarketMapping.target_type == target_type,
        SupermarketMapping.target_id == target_id,
        SupermarketMapping.active.is_(True),
    )
    if store is not None:
        statement = statement.where(SupermarketMapping.store == store)
    return session.exec(statement.order_by(SupermarketMapping.updated_at.desc())).first()


def create_or_replace_mapping(
    session: Session,
    target_type: SupermarketTargetType,
    target_id: int,
    payload: SupermarketMappingCreate,
) -> SupermarketMapping:
    _validate_target_exists(session, target_type, target_id)

    definition = get_store_definition(payload.store)
    if definition is None or not definition.supports_mapping:
        raise HTTPException(status_code=400, detail=f"Unsupported supermarket store: {payload.store.value}")

    # cache_id is mandatory: the snapshot fields are resolved from the cache row
    # server-side instead of trusting client-supplied strings.
    cache_row = session.get(SupermarketSearchCache, payload.cache_id)
    if cache_row is None:
        raise HTTPException(status_code=404, detail="Search cache entry not found")
    if cache_row.store != payload.store:
        raise HTTPException(status_code=400, detail="cache_id store does not match payload store")

    previous = get_active_mapping(session, target_type, target_id, payload.store)
    if previous is not None:
        previous.active = False
        previous.updated_at = datetime.now(UTC)
        session.add(previous)

    verified_at = payload.last_verified_at or datetime.now(UTC)
    mapping = SupermarketMapping(
        target_type=target_type,
        target_id=target_id,
        store=payload.store,
        external_id=cache_row.external_id,
        store_label=definition.label if definition else payload.store.value,
        name_snapshot=cache_row.name,
        category_snapshot=cache_row.category,
        packaging_snapshot=cache_row.packaging,
        price_snapshot=cache_row.price_text,
        product_url=cache_row.product_url,
        image_url=cache_row.image_url,
        last_verified_at=verified_at,
        active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping


def deactivate_mapping(session: Session, mapping_id: int) -> SupermarketMapping:
    mapping = session.get(SupermarketMapping, mapping_id)
    if mapping is None:
        raise HTTPException(status_code=404, detail="Supermarket mapping not found")

    mapping.active = False
    mapping.updated_at = datetime.now(UTC)
    session.add(mapping)
    session.commit()
    session.refresh(mapping)
    return mapping
