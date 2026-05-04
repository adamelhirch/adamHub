from __future__ import annotations

import uuid as uuid_lib
from typing import Any

import httpx

from app.services.scrapers.ubereats import (
    UbereatsAuthError,
    _build_client,
    load_ubereats_cookies,
)


CART_LOCALE = "fr"


class UbereatsCartError(RuntimeError):
    pass


def _add_locale(path: str) -> str:
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}localeCode={CART_LOCALE}"


async def _post(client: httpx.AsyncClient, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(_add_locale(path), json=body)
    if response.status_code in {401, 403}:
        raise UbereatsAuthError(
            "Uber Eats rejected the cart request. Refresh `data/cookies_ubereats.json`."
        )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success":
        raise UbereatsCartError(
            f"Uber Eats {path} failed: {payload.get('data')}"
        )
    return payload.get("data") or {}


async def list_active_carts(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    data = await _post(client, "/_p/api/getCartsViewForEaterUuidV1", {})
    carts_view = data.get("cartsView") or {}
    return list(carts_view.get("carts") or [])


async def get_draft_order(client: httpx.AsyncClient, draft_order_uuid: str) -> dict[str, Any]:
    """Fetch full draft order content via V2 (V1 returns a stripped shoppingCart)."""
    data = await _post(
        client,
        "/_p/api/getDraftOrderByUuidV2",
        {"draftOrderUUID": draft_order_uuid},
    )
    return data.get("draftOrder") or {}


async def find_cart_for_store(
    client: httpx.AsyncClient, store_uuid: str
) -> dict[str, Any] | None:
    """Returns {draft_order_uuid, cart_uuid, items[]} for the store, or None."""
    carts = await list_active_carts(client)
    for cart in carts:
        draft_uuid = cart.get("draftOrderUUID")
        if not draft_uuid:
            continue
        try:
            order = await get_draft_order(client, draft_uuid)
        except UbereatsCartError:
            continue
        shopping_cart = order.get("shoppingCart") or {}
        if shopping_cart.get("storeUuid") == store_uuid:
            return {
                "draft_order_uuid": draft_uuid,
                "cart_uuid": shopping_cart.get("cartUuid"),
                "items": shopping_cart.get("items") or [],
            }
    return None


def _shopping_cart_item_payload(item: dict[str, Any]) -> dict[str, Any]:
    """Convert a shoppingCart.items[] entry (from getDraftOrder) into the request schema."""
    return {
        "uuid": item["uuid"],
        "shoppingCartItemUuid": item["shoppingCartItemUuid"],
        "storeUuid": item["storeUuid"],
        "sectionUuid": item["sectionUuid"],
        "subsectionUuid": item["subsectionUuid"],
        "price": item.get("price", 0),
        "title": item.get("title", ""),
        "quantity": item.get("quantity", 1),
        "customizations": item.get("customizations") or {},
        "imageURL": item.get("imageURL") or "",
        "specialInstructions": item.get("specialInstructions") or "",
        "fulfillmentIssueAction": item.get("fulfillmentIssueAction") or {
            "type": "STORE_REPLACE_ITEM",
            "itemSubstitutes": None,
            "selectionSource": "UBER_SUGGESTED",
        },
        "pricedByUnit": item.get("pricedByUnit") or {"measurementType": "MEASUREMENT_TYPE_COUNT"},
        "soldByUnit": item.get("soldByUnit") or {"measurementType": "MEASUREMENT_TYPE_COUNT"},
    }


def _new_item_payload(
    *,
    store_uuid: str,
    item_uuid: str,
    section_uuid: str,
    subsection_uuid: str,
    title: str,
    price_cents: int,
    image_url: str | None,
    quantity: int,
) -> dict[str, Any]:
    return {
        "uuid": item_uuid,
        "shoppingCartItemUuid": str(uuid_lib.uuid4()),
        "storeUuid": store_uuid,
        "sectionUuid": section_uuid,
        "subsectionUuid": subsection_uuid,
        "price": price_cents,
        "title": title,
        "quantity": quantity,
        "customizations": {},
        "imageURL": image_url or "",
        "specialInstructions": "",
        "fulfillmentIssueAction": {
            "type": "STORE_REPLACE_ITEM",
            "itemSubstitutes": None,
            "selectionSource": "UBER_SUGGESTED",
        },
        "pricedByUnit": {"measurementType": "MEASUREMENT_TYPE_COUNT"},
        "soldByUnit": {"measurementType": "MEASUREMENT_TYPE_COUNT"},
    }


async def add_item_to_cart(
    *,
    store_uuid: str,
    item_uuid: str,
    section_uuid: str,
    subsection_uuid: str,
    title: str,
    price_cents: int,
    image_url: str | None,
    quantity: int = 1,
    cookies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create or extend the Uber Eats cart for `store_uuid` with the given item.

    If an item with the same `uuid` and `sectionUuid` already exists, increments
    its quantity. Otherwise appends. The full items list is sent to
    `createDraftOrderV2` which is idempotent (it overwrites the cart for that
    store, so we always send the merged list).
    """
    if cookies is None:
        cookies = load_ubereats_cookies()
    if not cookies:
        raise UbereatsAuthError(
            "No Uber Eats cookies on disk. Provide `data/cookies_ubereats.json`."
        )

    async with _build_client(cookies) as client:
        existing = await find_cart_for_store(client, store_uuid)
        items: list[dict[str, Any]] = []
        if existing:
            items = [_shopping_cart_item_payload(it) for it in existing["items"]]

        # If item already in cart (same product + section), bump quantity.
        merged = False
        for item in items:
            if item["uuid"] == item_uuid and item["sectionUuid"] == section_uuid:
                item["quantity"] = item.get("quantity", 1) + quantity
                merged = True
                break
        if not merged:
            items.append(
                _new_item_payload(
                    store_uuid=store_uuid,
                    item_uuid=item_uuid,
                    section_uuid=section_uuid,
                    subsection_uuid=subsection_uuid,
                    title=title,
                    price_cents=price_cents,
                    image_url=image_url,
                    quantity=quantity,
                )
            )

        body = {
            "removeAdapters": True,
            "isMulticart": True,
            "useCredits": True,
            "extraPaymentProfiles": [],
            "promotionOptions": {
                "autoApplyPromotionUUIDs": [],
                "selectedPromotionInstanceUUIDs": [],
                "skipApplyingPromotion": False,
            },
            "deliveryTime": {"asap": True},
            "deliveryType": "ASAP",
            "currencyCode": "EUR",
            "interactionType": "door_to_door",
            "checkMultipleDraftOrdersCap": True,
            "actionMeta": {"isQuickAdd": True},
            "analyticsRelevantData": {"profileSource": ""},
            "businessDetails": {},
            "shoppingCartItems": items,
        }
        data = await _post(client, "/_p/api/createDraftOrderV2", body)

    draft_order = data.get("draftOrder") or {}
    shopping_cart = draft_order.get("shoppingCart") or {}
    return {
        "draft_order_uuid": draft_order.get("uuid"),
        "cart_uuid": shopping_cart.get("cartUuid"),
        "items": shopping_cart.get("items") or [],
        "store_uuid": shopping_cart.get("storeUuid"),
    }


async def fetch_cart_summary(
    store_uuid: str | None = None,
    *,
    include_details: bool = False,
    cookies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return all active carts (and a focused one for `store_uuid` if provided).

    When `include_details=True`, also fetches the full draft order for each cart
    so the response carries items/cartUuid/storeUuid alongside the listing.
    """
    if cookies is None:
        cookies = load_ubereats_cookies()
    if not cookies:
        raise UbereatsAuthError(
            "No Uber Eats cookies on disk. Provide `data/cookies_ubereats.json`."
        )

    async with _build_client(cookies) as client:
        carts = await list_active_carts(client)
        focused: dict[str, Any] | None = None
        if store_uuid:
            focused = await find_cart_for_store(client, store_uuid)

        details_by_uuid: dict[str, dict[str, Any]] = {}
        if include_details:
            for cart in carts:
                draft_uuid = cart.get("draftOrderUUID")
                if not draft_uuid:
                    continue
                try:
                    order = await get_draft_order(client, draft_uuid)
                except UbereatsCartError:
                    continue
                shopping_cart = order.get("shoppingCart") or {}
                details_by_uuid[draft_uuid] = {
                    "cart_uuid": shopping_cart.get("cartUuid"),
                    "store_uuid": shopping_cart.get("storeUuid"),
                    "items": shopping_cart.get("items") or [],
                }

    summary_carts = []
    for cart in carts:
        draft_uuid = cart.get("draftOrderUUID")
        details = details_by_uuid.get(draft_uuid or "") if include_details else None
        summary_carts.append(
            {
                "draft_order_uuid": draft_uuid,
                "title": cart.get("title"),
                "subtotal_text": (cart.get("tagline2") or {}).get("text"),
                "item_count": cart.get("itemCount"),
                "store_image_urls": cart.get("storeImageUrls") or [],
                "details": details,
            }
        )
    return {"carts": summary_carts, "focused": focused}
