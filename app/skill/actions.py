import asyncio
import concurrent.futures
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlmodel import select

from app.api._crud import apply_updates, create, delete, save
from app.models import (
    GroceryItem,
    GroceryPantrySync,
    MealPlan,
    MealPlanCookConfirmation,
    MealSlot,
    PantryItem,
    Recipe,
    RecipeIngredient,
    SupermarketCart,
    SupermarketCartItem,
    SupermarketConnection,
    SupermarketSearchCache,
    SupermarketStore,
    User,
)
from app.schemas import (
    CreateCartJobPayload,
    GroceryItemCreate,
    GroceryItemUpdate,
    MealPlanCreate,
    MealPlanUpdate,
    PantryItemCreate,
    PantryItemUpdate,
    RecipeCreate,
    RecipeUpdate,
    SupermarketCartItemRead,
    SupermarketCartRead,
    UserStorePreferenceUpdate,
)
from app.services.cook import (
    confirm_meal_plan_cooked,
    confirm_recipe_cooked,
    reset_meal_plan_cook_confirmation,
    unconfirm_meal_plan_cooked,
    unconfirm_recipe_cooked,
)
from app.services.meal_planning import (
    build_meal_plan_read,
    build_meal_plan_reads,
    build_recipe_read,
    resolve_recipe_ingredient_fields,
    sync_meal_plan_to_grocery,
    validate_meal_plan_slot_free,
    visible_meal_plans,
)
from app.services.grocery_pantry import (
    build_pantry_overview,
    sync_checked_grocery_item_to_pantry,
)
from app.services.openfoodfacts import lookup_openfoodfacts_barcode
from app.services.connections import (
    activate_connection as activate_supermarket_connection,
    delete_connection as delete_supermarket_connection,
    list_connections as list_supermarket_connections,
    upsert_connection as upsert_supermarket_connection,
    decrypt_cookies as decrypt_connection_cookies,
)
from app.services.store_catalog import (
    fetch_search_results,
    get_selected_store as get_selected_supermarket_store,
    list_store_definitions,
    load_active_cookies,
    upsert_search_cache,
    upsert_selected_store,
)
from app.services.scrapers.auchan import (
    AuchanAuthError,
    AuchanStoreContext,
    list_auchan_offering_contexts,
    load_auchan_cookies,
    select_auchan_store,
)
from app.services import cart, cart_mirror
from app.services.supermarket.cart_job_service import CartJobService
from app.services.supermarket.store_locator import SupermarketStoreLocator


def _run_sync(coro):
    """Run an async coroutine synchronously, even if already inside a running event loop (e.g. MCP)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _as_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off"}:
            return False
    return bool(value)


def _clamp_int(value, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _int_id(payload: dict, field: str) -> int:
    """Parse a scalar record id from a skill payload, raising ValueError on malformed input."""
    value = payload.get(field)
    if value is None:
        raise ValueError(f"{field} is required")
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field} must be an integer") from exc
    raise ValueError(f"{field} must be an integer")


def _parse_datetime(value, field_name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        raw = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be ISO datetime") from exc
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise ValueError(f"{field_name} must be datetime")


def _parse_date(value, field_name: str) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        v = value.strip()
        if "T" in v:
            v = v.split("T")[0]
        elif " " in v:
            v = v.split(" ")[0]
        try:
            return date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be in YYYY-MM-DD format") from exc
    raise ValueError(f"{field_name} must be in YYYY-MM-DD format")


def _opt_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_SLOT_DEFAULT_TIME: dict[str, time] = {
    "breakfast": time(hour=8, minute=0),
    "lunch": time(hour=12, minute=30),
    "dinner": time(hour=19, minute=30),
}


def _resolve_meal_planned_at(payload: dict, current: datetime | None = None) -> datetime:
    planned_at = _parse_datetime(payload.get("planned_at"), "planned_at")
    if planned_at is not None:
        return planned_at

    planned_for = _parse_date(payload.get("planned_for"), "planned_for")
    if planned_for is not None:
        slot = str(payload.get("slot") or "").strip().lower()
        slot_time = _SLOT_DEFAULT_TIME.get(slot, time(hour=12, minute=0))
        return datetime.combine(planned_for, slot_time).replace(tzinfo=timezone.utc)

    if current is not None:
        return current
    return datetime.now(timezone.utc)


def _get_owned_recipe(session, recipe_id: int, user_id: int) -> Recipe:
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    return recipe


def _get_owned_meal_plan(session, meal_plan_id: int, user_id: int) -> MealPlan:
    plan = session.get(MealPlan, meal_plan_id)
    if not plan or plan.user_id != user_id:
        raise ValueError("meal_plan_id not found")
    return plan


def _is_owner_user(user: User | None) -> bool:
    """True when the acting user is the configured ADAMHUB_OWNER_EMAIL user."""
    if user is None:
        return False
    from app.core.config import get_settings

    settings = get_settings()
    owner_email = (settings.owner_email or "").strip().lower()
    return bool(owner_email) and (user.email or "").strip().lower() == owner_email


def _connection_is_operable(connection, user: User | None) -> bool:
    """A connection can be listed/activated/deleted by the acting user."""
    if connection is None:
        return True
    if connection.user_id is not None:
        return user is not None and connection.user_id == user.id
    return _is_owner_user(user)


# ── Supermarket Handlers ──────────────────────────────────────────────────

def _handle_supermarket_list_stores(payload, session, *, user, now, user_id):
    return {
        "stores": [
            {
                "key": definition.key.value,
                "label": definition.label,
                "supports_search": definition.supports_search,
                "supports_mapping": definition.supports_mapping,
                "supports_cart_automation": definition.supports_cart_automation,
                "scraper_name": definition.scraper_name,
                "notes": definition.notes,
            }
            for definition in list_store_definitions()
        ]
    }


def _handle_supermarket_list_connections(payload, session, *, user, now, user_id):
    store_key = payload.get("store")
    store_enum = SupermarketStore(store_key.lower()) if store_key else None
    rows = list_supermarket_connections(session, store_enum, user_id=user_id)
    if _is_owner_user(user):
        rows += list_supermarket_connections(session, store_enum, user_id=None)

    def _read(row):
        try:
            count = len(decrypt_connection_cookies(row))
        except Exception:
            count = 0
        return {
            "id": row.id,
            "store": row.store.value,
            "label": row.label,
            "is_active": row.is_active,
            "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "cookies_count": count,
        }

    return {"connections": [_read(r) for r in rows]}


def _handle_supermarket_import_connection(payload, session, *, user, now, user_id):
    store_enum = SupermarketStore(str(payload.get("store") or "").lower())
    cookies = payload.get("cookies") or []
    credentials = payload.get("credentials")
    if not isinstance(cookies, list):
        raise ValueError("cookies must be a list")
    if not cookies and not isinstance(credentials, dict):
        raise ValueError("cookies or credentials are required")
    label = (payload.get("label") or "").strip() or f"{store_enum.value}-connection"
    connection = upsert_supermarket_connection(
        session,
        store=store_enum,
        label=label,
        cookies=cookies,
        credentials=credentials,
        activate=_as_bool(payload.get("activate"), default=True),
        connection_id=payload.get("connection_id"),
        user_id=user_id,
    )
    return {
        "connection": {
            "id": connection.id,
            "store": connection.store.value,
            "label": connection.label,
            "is_active": connection.is_active,
            "cookies_count": len(cookies),
        }
    }


def _handle_supermarket_activate_connection(payload, session, *, user, now, user_id):
    connection_id = _int_id(payload, "connection_id")
    if not connection_id:
        raise ValueError("connection_id is required")
    existing = session.get(SupermarketConnection, connection_id)
    if not _connection_is_operable(existing, user):
        raise ValueError("Connection not found")
    connection = activate_supermarket_connection(session, connection_id, user_id=user_id)
    if connection is None:
        raise ValueError("Connection not found")
    return {"connection": {"id": connection.id, "store": connection.store.value, "is_active": True}}


def _handle_supermarket_delete_connection(payload, session, *, user, now, user_id):
    connection_id = _int_id(payload, "connection_id")
    if not connection_id:
        raise ValueError("connection_id is required")
    existing = session.get(SupermarketConnection, connection_id)
    if not _connection_is_operable(existing, user):
        raise ValueError("Connection not found")
    connection = delete_supermarket_connection(session, connection_id, user_id=user_id)
    if connection is None:
        raise ValueError("Connection not found")
    return {"deleted": True, "id": connection_id}


def _handle_supermarket_search(payload, session, *, user, now, user_id):
    store_key = (payload.get("store") or "intermarche").lower()
    if store_key not in ("intermarche", "carrefour", "leclerc", "auchan"):
        raise ValueError(
            "supermarket.search supports 'intermarche', 'carrefour', 'leclerc' or 'auchan'."
        )
    store_enum = SupermarketStore(store_key)
    queries = payload.get("queries")
    if isinstance(queries, str):
        queries = [queries]
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries must be a non-empty list")
    max_results = _clamp_int(payload.get("max_results"), default=10, minimum=1, maximum=30)
    promotions_only = _as_bool(payload.get("promotions_only"), default=False)
    try:
        results = _run_sync(
            fetch_search_results(
                store=store_enum,
                queries=[str(query).strip() for query in queries if str(query).strip()],
                max_results=max_results,
                promotions_only=promotions_only,
                session=session,
                user_id=user_id,
            )
        )
    except RuntimeError as exc:
        raise ValueError(f"supermarket.search failed: {exc}") from exc
    saved = upsert_search_cache(session, store_enum, results)
    return {"results": [row.model_dump(mode="json") for row in saved]}


def _handle_supermarket_list_offering_contexts(payload, session, *, user, now, user_id):
    zipcode = str(payload.get("zipcode") or "").strip()
    city = str(payload.get("city") or "").strip()
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    if not zipcode or not city:
        raise ValueError("zipcode and city are required")
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        raise ValueError("latitude and longitude are required numbers") from None

    cookies = load_active_cookies(session, SupermarketStore.AUCHAN) or load_auchan_cookies()
    try:
        contexts = _run_sync(
            list_auchan_offering_contexts(
                zipcode=zipcode,
                city=city,
                latitude=latitude,
                longitude=longitude,
                country=str(payload.get("country") or "France"),
                cookies=cookies,
            )
        )
    except AuchanAuthError as exc:
        raise ValueError(f"supermarket.list_offering_contexts failed: {exc}") from exc
    except RuntimeError as exc:
        raise ValueError(f"supermarket.list_offering_contexts failed: {exc}") from exc
    return {"contexts": contexts}


def _handle_supermarket_select_auchan_store(payload, session, *, user, now, user_id):
    seller_id = str(payload.get("seller_id") or "").strip()
    store_reference = str(payload.get("store_reference") or "").strip()
    store_label = str(payload.get("store_label") or "").strip()
    if not seller_id or not store_reference or not store_label:
        raise ValueError("seller_id, store_reference and store_label are required")

    cookies = load_active_cookies(session, SupermarketStore.AUCHAN) or load_auchan_cookies()
    context = AuchanStoreContext(
        seller_id=seller_id,
        store_reference=store_reference,
        channel=str(payload.get("channel") or "PICK_UP"),
        zipcode=payload.get("zipcode"),
        city=payload.get("city"),
        country=payload.get("country") or "France",
        latitude=_opt_float(payload.get("latitude")),
        longitude=_opt_float(payload.get("longitude")),
    )
    try:
        journey = _run_sync(select_auchan_store(context, cookies=cookies))
    except AuchanAuthError as exc:
        raise ValueError(f"supermarket.select_auchan_store failed: {exc}") from exc
    except RuntimeError as exc:
        raise ValueError(f"supermarket.select_auchan_store failed: {exc}") from exc

    selection = upsert_selected_store(
        session,
        SupermarketStore.AUCHAN,
        external_store_id=seller_id,
        store_label=store_label,
        location_label=payload.get("location_label"),
        raw_payload={
            "store_reference": store_reference,
            "channel": context.channel,
            "zipcode": context.zipcode,
            "city": context.city,
            "country": context.country,
            "latitude": context.latitude,
            "longitude": context.longitude,
            "journey_id": journey.get("id"),
        },
    )
    return {
        "selection": {
            "external_store_id": selection.external_store_id,
            "store_label": selection.store_label,
            "location_label": selection.location_label,
            "updated_at": selection.updated_at.isoformat(),
        }
    }


def _serialize_cart(session, cart_obj) -> dict:
    items = session.exec(
        select(SupermarketCartItem)
        .where(SupermarketCartItem.cart_id == cart_obj.id)
        .order_by(SupermarketCartItem.id)
    ).all()
    item_reads = [SupermarketCartItemRead.model_validate(item, from_attributes=True) for item in items]
    total_amount = sum((it.price_amount or 0.0) * it.quantity for it in item_reads)
    read_obj = SupermarketCartRead(
        id=cart_obj.id,
        store=cart_obj.store,
        status=cart_obj.status,
        validated_at=cart_obj.validated_at,
        external_cart_ref=cart_obj.external_cart_ref,
        created_at=cart_obj.created_at,
        updated_at=cart_obj.updated_at,
        items=item_reads,
    )
    dumped = read_obj.model_dump(mode="json")
    dumped["total_amount"] = round(total_amount, 2)
    dumped["items_count"] = sum(it.quantity for it in item_reads)
    return dumped


def _handle_supermarket_get_cart(payload, session, *, user, now, user_id):
    store_key = (payload.get("store") or "intermarche").lower()
    if store_key not in ("intermarche", "carrefour", "leclerc", "auchan"):
        raise ValueError("store must be one of: 'intermarche', 'carrefour', 'leclerc', 'auchan'")
    store_enum = SupermarketStore(store_key)
    force_sync = _as_bool(payload.get("force_sync"), default=True)
    if force_sync:
        try:
            cart_obj = _run_sync(cart_mirror.read_cart(session, user_id, store=store_enum))
        except HTTPException as exc:
            raise ValueError(f"supermarket.get_cart failed: {exc.detail}") from exc
        except Exception as exc:
            raise ValueError(f"supermarket.get_cart failed: {exc}") from exc
    else:
        cart_obj = cart.upsert_cart(session, store_enum, user_id=user_id)
    return _serialize_cart(session, cart_obj)


def _handle_supermarket_list_carts(payload, session, *, user, now, user_id):
    carts = cart.list_carts(session, user_id=user_id)
    return {"carts": [_serialize_cart(session, c) for c in carts]}


def _handle_supermarket_add_cart_item(payload, session, *, user, now, user_id):
    store_key = (payload.get("store") or "intermarche").lower()
    if store_key not in ("intermarche", "carrefour", "leclerc", "auchan"):
        raise ValueError("store must be one of: 'intermarche', 'carrefour', 'leclerc', 'auchan'")
    store_enum = SupermarketStore(store_key)
    cache_id = payload.get("cache_id")
    if not cache_id:
        raise ValueError("cache_id is required")
    try:
        cache_id = int(cache_id)
    except (TypeError, ValueError):
        raise ValueError("cache_id must be an integer")
    quantity = _clamp_int(payload.get("quantity"), default=1, minimum=1, maximum=99)
    try:
        cart_obj = _run_sync(
            cart_mirror.add_item(session, user_id, cache_id, quantity=quantity, store=store_enum)
        )
    except HTTPException as exc:
        raise ValueError(f"supermarket.add_cart_item failed: {exc.detail}") from exc
    except Exception as exc:
        raise ValueError(f"supermarket.add_cart_item failed: {exc}") from exc
    return _serialize_cart(session, cart_obj)


def _handle_supermarket_update_cart_item(payload, session, *, user, now, user_id):
    store_key = (payload.get("store") or "intermarche").lower()
    if store_key not in ("intermarche", "carrefour", "leclerc", "auchan"):
        raise ValueError("store must be one of: 'intermarche', 'carrefour', 'leclerc', 'auchan'")
    store_enum = SupermarketStore(store_key)
    item_id = payload.get("item_id")
    if not item_id:
        raise ValueError("item_id is required")
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        raise ValueError("item_id must be an integer")
    quantity = int(payload.get("quantity", 1))
    try:
        if quantity <= 0:
            cart_obj = _run_sync(
                cart_mirror.remove_item(session, user_id, item_id, store=store_enum)
            )
        else:
            cart_obj = _run_sync(
                cart_mirror.update_item_quantity(session, user_id, item_id, quantity=quantity, store=store_enum)
            )
    except HTTPException as exc:
        raise ValueError(f"supermarket.update_cart_item failed: {exc.detail}") from exc
    except Exception as exc:
        raise ValueError(f"supermarket.update_cart_item failed: {exc}") from exc
    return _serialize_cart(session, cart_obj)


def _handle_supermarket_remove_cart_item(payload, session, *, user, now, user_id):
    store_key = (payload.get("store") or "intermarche").lower()
    if store_key not in ("intermarche", "carrefour", "leclerc", "auchan"):
        raise ValueError("store must be one of: 'intermarche', 'carrefour', 'leclerc', 'auchan'")
    store_enum = SupermarketStore(store_key)
    item_id = payload.get("item_id")
    if not item_id:
        raise ValueError("item_id is required")
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        raise ValueError("item_id must be an integer")
    try:
        cart_obj = _run_sync(
            cart_mirror.remove_item(session, user_id, item_id, store=store_enum)
        )
    except HTTPException as exc:
        raise ValueError(f"supermarket.remove_cart_item failed: {exc.detail}") from exc
    except Exception as exc:
        raise ValueError(f"supermarket.remove_cart_item failed: {exc}") from exc
    return _serialize_cart(session, cart_obj)


def _handle_supermarket_clear_cart(payload, session, *, user, now, user_id):
    store_key = (payload.get("store") or "intermarche").lower()
    if store_key not in ("intermarche", "carrefour", "leclerc", "auchan"):
        raise ValueError("store must be one of: 'intermarche', 'carrefour', 'leclerc', 'auchan'")
    store_enum = SupermarketStore(store_key)
    try:
        cart_obj = _run_sync(cart_mirror.clear_cart(session, user_id, store=store_enum))
    except HTTPException as exc:
        raise ValueError(f"supermarket.clear_cart failed: {exc.detail}") from exc
    except Exception as exc:
        raise ValueError(f"supermarket.clear_cart failed: {exc}") from exc
    return _serialize_cart(session, cart_obj)


def _handle_supermarket_search_stores(payload, session, *, user, now, user_id):
    store_str = payload.get("store")
    store = SupermarketStore(store_str.lower()) if store_str else None
    zipcode = payload.get("zipcode")
    city = payload.get("city")
    lat = _opt_float(payload.get("latitude"))
    lng = _opt_float(payload.get("longitude"))

    try:
        stores = _run_sync(
            SupermarketStoreLocator.search_stores(
                session=session,
                store=store,
                zipcode=zipcode,
                city=city,
                latitude=lat,
                longitude=lng,
            )
        )
    except Exception as exc:
        raise ValueError(f"supermarket.search_stores failed: {exc}") from exc

    return {"stores": [s.model_dump(mode="json") for s in stores]}


def _handle_supermarket_set_favorite_store(payload, session, *, user, now, user_id):
    if user_id is None:
        raise ValueError("User context required to set favorite supermarket store")
    store_key = payload.get("store")
    if not store_key:
        raise ValueError("store is required")
    store = SupermarketStore(store_key.lower())
    external_store_id = payload.get("external_store_id")
    if not external_store_id:
        raise ValueError("external_store_id is required")

    pref_payload = UserStorePreferenceUpdate(
        external_store_id=external_store_id,
        store_label=payload.get("store_label") or f"{store.value.capitalize()} Drive",
        location_label=payload.get("location_label"),
        pickup_type=payload.get("pickup_type") or "quai",
        optimization_strategy=payload.get("optimization_strategy") or "mdd",
    )
    pref = SupermarketStoreLocator.set_user_preference(session, user_id, store, pref_payload)
    return {
        "preference": {
            "store": pref.store.value,
            "external_store_id": pref.external_store_id,
            "store_label": pref.store_label,
            "location_label": pref.location_label,
            "pickup_type": pref.pickup_type,
            "optimization_strategy": pref.optimization_strategy,
            "updated_at": pref.updated_at.isoformat(),
        }
    }


def _handle_supermarket_prepare_cart(payload, session, *, user, now, user_id):
    if user_id is None:
        raise ValueError("User context required to prepare supermarket cart")
    store_key = payload.get("store") or "leclerc"
    store = SupermarketStore(store_key.lower())
    strategy = payload.get("optimization_strategy") or "mdd"
    item_ids = payload.get("item_ids") or []

    job_payload = CreateCartJobPayload(
        store=store,
        external_store_id=payload.get("external_store_id"),
        optimization_strategy=strategy,
        item_ids=item_ids,
    )
    job = CartJobService.create_draft_job(session, user_id, job_payload)
    dto = CartJobService.job_to_read_dto(session, job)
    return {"job": dto.model_dump(mode="json")}


def _handle_supermarket_confirm_cart_sync(payload, session, *, user, now, user_id):
    if user_id is None:
        raise ValueError("User context required to sync supermarket cart")
    job_id = payload.get("job_id")
    if not job_id:
        raise ValueError("job_id is required")
    try:
        res = CartJobService.sync_remote_cart(session, user_id, int(job_id))
    except HTTPException as exc:
        raise ValueError(f"supermarket.confirm_cart_sync failed: {exc.detail}") from exc
    return {"sync": res.model_dump(mode="json")}


def _handle_supermarket_confirm_pickup(payload, session, *, user, now, user_id):
    if user_id is None:
        raise ValueError("User context required to confirm pickup")
    job_id = payload.get("job_id")
    if not job_id:
        raise ValueError("job_id is required")
    try:
        res = CartJobService.confirm_pickup(session, user_id, int(job_id))
    except HTTPException as exc:
        raise ValueError(f"supermarket.confirm_pickup failed: {exc.detail}") from exc
    return {"pickup": res.model_dump(mode="json")}


# ── Grocery Handlers ──────────────────────────────────────────────────────

def _handle_grocery_add_item(payload, session, *, user, now, user_id):
    data = GroceryItemCreate.model_validate(payload)
    item = create(session, GroceryItem(**data.model_dump(), user_id=user_id))
    return {"item": item.model_dump(mode="json")}


def _handle_grocery_list_items(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=200, minimum=1, maximum=500)
    statement = (
        select(GroceryItem)
        .where(GroceryItem.user_id == user_id)
        .order_by(GroceryItem.checked.asc(), GroceryItem.priority.asc())
        .limit(limit)
    )
    if payload.get("checked") is not None:
        statement = statement.where(GroceryItem.checked == _as_bool(payload.get("checked")))

    items = session.exec(statement).all()
    return {"items": [item.model_dump(mode="json") for item in items]}


def _handle_grocery_update_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(GroceryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")

    was_checked = item.checked
    patch = GroceryItemUpdate.model_validate({k: v for k, v in payload.items() if k != "item_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No grocery fields to update")

    apply_updates(item, updates, touch=True)
    item = save(session, item)
    pantry_sync = None
    if not was_checked and item.checked:
        pantry_sync = sync_checked_grocery_item_to_pantry(session, item, user_id=user_id)
        session.refresh(item)
    return {"item": item.model_dump(mode="json"), "pantry_sync": pantry_sync}


def _handle_grocery_check_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    checked = _as_bool(payload.get("checked"), default=True)
    item = session.get(GroceryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")
    was_checked = item.checked
    item.checked = checked
    item.updated_at = now
    item = save(session, item)
    pantry_sync = None
    if not was_checked and item.checked:
        pantry_sync = sync_checked_grocery_item_to_pantry(session, item, user_id=user_id)
        session.refresh(item)
    return {"item": item.model_dump(mode="json"), "pantry_sync": pantry_sync}


def _handle_grocery_delete_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(GroceryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")
    sync_rows = session.exec(
        select(GroceryPantrySync).where(GroceryPantrySync.grocery_item_id == item_id)
    ).all()
    for row in sync_rows:
        session.delete(row)
    if sync_rows:
        session.commit()
    delete(session, item)
    return {"ok": True, "deleted_id": item_id}


# ── Recipe Handlers ───────────────────────────────────────────────────────

def _handle_recipe_add(payload, session, *, user, now, user_id):
    data = RecipeCreate.model_validate(payload)
    recipe = Recipe(
        name=data.name,
        description=data.description,
        instructions=data.instructions,
        steps=data.steps,
        utensils=data.utensils,
        prep_minutes=data.prep_minutes,
        cook_minutes=data.cook_minutes,
        servings=data.servings,
        tags=data.tags,
        source_url=data.source_url,
        source_platform=data.source_platform,
        source_title=data.source_title,
        source_description=data.source_description,
        source_transcript=data.source_transcript,
        user_id=user_id,
    )
    session.add(recipe)
    session.commit()
    session.refresh(recipe)

    for ing in data.ingredients:
        ingredient = RecipeIngredient(recipe_id=recipe.id, **resolve_recipe_ingredient_fields(session, ing))
        session.add(ingredient)
    session.commit()

    recipe = session.get(Recipe, recipe.id)
    return {"recipe": build_recipe_read(session, recipe).model_dump(mode="json")}


def _handle_recipe_update(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")

    patch = RecipeUpdate.model_validate({k: v for k, v in payload.items() if k != "recipe_id"})
    updates = patch.model_dump(exclude_unset=True)
    ingredients = updates.pop("ingredients", None)

    for key, value in updates.items():
        setattr(recipe, key, value)
    recipe.updated_at = now
    session.add(recipe)
    session.commit()

    if ingredients is not None:
        existing = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)).all()
        for row in existing:
            session.delete(row)
        session.commit()
        for ing in ingredients:
            ingredient = RecipeIngredient(recipe_id=recipe.id, **resolve_recipe_ingredient_fields(session, ing))
            session.add(ingredient)
        recipe.updated_at = now
        session.add(recipe)
        session.commit()

    session.refresh(recipe)
    return {"recipe": build_recipe_read(session, recipe).model_dump(mode="json")}


def _handle_recipe_list(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=20, minimum=1, maximum=100)
    recipes = session.exec(
        select(Recipe)
        .where(Recipe.user_id == user_id)
        .order_by(Recipe.created_at.desc())
        .limit(limit)
    ).all()
    data = [build_recipe_read(session, recipe).model_dump(mode="json") for recipe in recipes]
    return {"recipes": data}


def _handle_recipe_get(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    return {"recipe": build_recipe_read(session, recipe).model_dump(mode="json")}


def _handle_recipe_confirm_cooked(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    servings_override = None
    if payload.get("servings_override") is not None:
        try:
            servings_override = int(payload["servings_override"])
        except (TypeError, ValueError) as exc:
            raise ValueError("servings_override must be an integer") from exc
    result = confirm_recipe_cooked(session, recipe, servings_override, payload.get("note"), user_id=user_id)
    return {
        "recipe_id": recipe.id,
        "recipe_name": recipe.name,
        "cooked_at": result.get("confirmed_at"),
        "note": result.get("note"),
        "missing_ingredients": [item.model_dump(mode="json") for item in result.get("missing_ingredients", [])],
        "pantry_consumption": result.get("pantry_consumption", []),
        "meal_plan_id": result.get("meal_plan_id"),
        "already_confirmed": bool(result.get("already_confirmed")),
    }


def _handle_recipe_unconfirm_cooked(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    result = unconfirm_recipe_cooked(session, recipe, user_id=user_id)
    return {
        "recipe_id": recipe.id,
        "recipe_name": recipe.name,
        "already_unconfirmed": bool(result.get("already_unconfirmed")),
        "previously_confirmed_at": result.get("previously_confirmed_at"),
        "note": result.get("note"),
        "pantry_restore": result.get("pantry_restore", []),
    }


def _handle_recipe_delete(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    recipe = session.get(Recipe, recipe_id)
    if not recipe or recipe.user_id != user_id:
        raise ValueError("recipe_id not found")
    ingredient_rows = session.exec(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)).all()
    for row in ingredient_rows:
        session.delete(row)
    if ingredient_rows:
        session.commit()

    meal_plans = session.exec(
        select(MealPlan).where(MealPlan.recipe_id == recipe.id, MealPlan.user_id == user_id)
    ).all()
    for plan in meal_plans:
        confirmation = session.exec(
            select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == plan.id)
        ).first()
        if confirmation:
            session.delete(confirmation)
        session.delete(plan)
    if meal_plans:
        session.commit()

    session.delete(recipe)
    session.commit()
    return {"ok": True, "deleted_id": recipe_id}


# ── Meal Plan Handlers ────────────────────────────────────────────────────

def _handle_meal_plan_add(payload, session, *, user, now, user_id):
    if "slot" in payload and isinstance(payload["slot"], str):
        s = payload["slot"].lower()
        if "breakfast" in s:
            payload["slot"] = "breakfast"
        elif "lunch" in s:
            payload["slot"] = "lunch"
        elif "dinner" in s:
            payload["slot"] = "dinner"
    data = MealPlanCreate.model_validate(payload)
    _get_owned_recipe(session, data.recipe_id, user_id)

    planned_at = _resolve_meal_planned_at(payload)
    planned_for = _parse_date(payload.get("planned_for"), "planned_for") or planned_at.date()
    slot = data.slot
    validate_meal_plan_slot_free(
        session,
        user_id=user_id,
        planned_for=planned_for,
        slot=slot,
    )
    plan = MealPlan(**data.model_dump(exclude={"planned_at"}), planned_at=planned_at, user_id=user_id)
    if plan.planned_for is None:
        plan.planned_for = planned_at.date()
    session.add(plan)
    session.commit()
    session.refresh(plan)

    added_count = 0
    missing_items = []
    if plan.auto_add_missing_ingredients:
        added_count, missing_items = sync_meal_plan_to_grocery(session, plan, user_id=user_id)
    return {
        "meal_plan": build_meal_plan_read(session, plan, user_id=user_id).model_dump(mode="json"),
        "groceries_added_count": added_count,
        "missing_ingredients": [
            m.model_dump(mode="json") if hasattr(m, "model_dump") else m for m in missing_items
        ],
    }


def _handle_meal_plan_list(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=100, minimum=1, maximum=400)
    date_from = _parse_date(payload.get("date_from"), "date_from") if payload.get("date_from") else None
    date_to = _parse_date(payload.get("date_to"), "date_to") if payload.get("date_to") else None
    slot = MealSlot(payload.get("slot")) if payload.get("slot") else None
    plans = visible_meal_plans(
        session,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        slot=slot,
        limit=limit,
    )
    return {
        "meal_plans": [
            read.model_dump(mode="json") for read in build_meal_plan_reads(session, plans, user_id=user_id)
        ]
    }


def _handle_meal_plan_update(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    patch = MealPlanUpdate.model_validate({k: v for k, v in payload.items() if k != "meal_plan_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No meal plan fields to update")
    if "recipe_id" in updates:
        _get_owned_recipe(session, updates["recipe_id"], user_id)

    next_planned_at = _resolve_meal_planned_at({**payload, **updates}, current=plan.planned_at)
    next_planned_for = updates.get("planned_for", plan.planned_for)
    if next_planned_for is None:
        next_planned_for = next_planned_at.date()
    next_slot = updates.get("slot", plan.slot)
    validate_meal_plan_slot_free(
        session,
        user_id=user_id,
        planned_for=next_planned_for,
        slot=next_slot,
        exclude_plan_id=plan.id,
    )

    reset_cook_confirmation = (
        ("planned_at" in updates and updates.get("planned_at") != plan.planned_at)
        or ("planned_for" in updates and updates.get("planned_for") != plan.planned_for)
        or ("slot" in updates and updates.get("slot") != plan.slot)
        or ("recipe_id" in updates and updates.get("recipe_id") != plan.recipe_id)
        or ("servings_override" in updates and updates.get("servings_override") != plan.servings_override)
    )

    for key, value in updates.items():
        setattr(plan, key, value)
    plan.planned_at = next_planned_at
    plan.planned_for = next_planned_for
    if reset_cook_confirmation:
        reset_meal_plan_cook_confirmation(session, plan)
    plan.updated_at = now
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return {"meal_plan": build_meal_plan_read(session, plan, user_id=user_id).model_dump(mode="json")}


def _handle_meal_plan_delete(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    confirmation = session.exec(
        select(MealPlanCookConfirmation).where(MealPlanCookConfirmation.meal_plan_id == plan.id)
    ).first()
    if confirmation:
        session.delete(confirmation)
        session.commit()
    session.delete(plan)
    session.commit()
    return {"ok": True, "deleted_id": meal_plan_id}


def _handle_meal_plan_sync_groceries(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    created, missing = sync_meal_plan_to_grocery(session, plan, user_id=user_id)
    return {
        "meal_plan_id": meal_plan_id,
        "created_grocery_items": created,
        "missing_ingredients": [item.model_dump(mode="json") for item in missing],
    }


def _handle_meal_plan_confirm_cooked(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    result = confirm_meal_plan_cooked(session, plan, note=payload.get("note"), user_id=user_id)
    return {
        "meal_plan_id": meal_plan_id,
        "already_confirmed": bool(result.get("already_confirmed")),
        "confirmed_at": result.get("confirmed_at"),
        "note": result.get("note"),
        "pantry_consumption": result.get("pantry_consumption", []),
    }


def _handle_meal_plan_log_cooked(payload, session, *, user, now, user_id):
    recipe_id = _int_id(payload, "recipe_id")
    _get_owned_recipe(session, recipe_id, user_id)
    cooked_at = _parse_datetime(payload.get("cooked_at"), "cooked_at") or now
    plan = MealPlan(
        recipe_id=recipe_id,
        planned_at=cooked_at,
        planned_for=cooked_at.date(),
        servings_override=payload.get("servings_override"),
        note=payload.get("note") or "cooked without explicit planning",
        auto_add_missing_ingredients=False,
        user_id=user_id,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    result = confirm_meal_plan_cooked(session, plan, note=payload.get("note"), user_id=user_id)
    return {
        "meal_plan": build_meal_plan_read(session, plan, user_id=user_id).model_dump(mode="json"),
        "confirmation": result,
    }


def _handle_meal_plan_unconfirm_cooked(payload, session, *, user, now, user_id):
    meal_plan_id = _int_id(payload, "meal_plan_id")
    plan = _get_owned_meal_plan(session, meal_plan_id, user_id)
    result = unconfirm_meal_plan_cooked(session, plan, user_id=user_id)
    return {
        "meal_plan_id": meal_plan_id,
        "already_unconfirmed": bool(result.get("already_unconfirmed")),
        "previously_confirmed_at": result.get("previously_confirmed_at"),
        "note": result.get("note"),
        "pantry_restore": result.get("pantry_restore", []),
    }


# ── Pantry Handlers ───────────────────────────────────────────────────────

def _handle_pantry_add_item(payload, session, *, user, now, user_id):
    data = PantryItemCreate.model_validate(payload)
    item = create(session, PantryItem(**data.model_dump(), user_id=user_id))
    return {"item": item.model_dump(mode="json")}


def _handle_pantry_list_items(payload, session, *, user, now, user_id):
    limit = _clamp_int(payload.get("limit"), default=500, minimum=1, maximum=1000)
    low_stock_only = _as_bool(payload.get("low_stock_only"), default=False)
    expiring_in_days = payload.get("expiring_in_days")

    statement = (
        select(PantryItem)
        .where(PantryItem.user_id == user_id)
        .order_by(PantryItem.updated_at.desc())
        .limit(limit)
    )
    if low_stock_only:
        statement = statement.where(PantryItem.quantity <= PantryItem.min_quantity)
    if expiring_in_days is not None:
        days = _clamp_int(expiring_in_days, default=7, minimum=1, maximum=3650)
        until = date.today() + timedelta(days=days)
        statement = statement.where(PantryItem.expires_at.is_not(None), PantryItem.expires_at <= until)

    items = session.exec(statement).all()
    return {"items": [item.model_dump(mode="json") for item in items]}


def _handle_pantry_update_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(PantryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")

    patch = PantryItemUpdate.model_validate({k: v for k, v in payload.items() if k != "item_id"})
    updates = patch.model_dump(exclude_unset=True)
    if not updates:
        raise ValueError("No pantry fields to update")

    apply_updates(item, updates, touch=True)
    item = save(session, item)
    return {"item": item.model_dump(mode="json")}


def _handle_pantry_consume_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    amount = float(payload.get("amount", 0))
    if amount <= 0:
        raise ValueError("amount must be > 0")

    item = session.get(PantryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")

    item.quantity = max(0.0, item.quantity - amount)
    item.updated_at = now
    item = save(session, item)
    return {"item": item.model_dump(mode="json")}


def _handle_pantry_delete_item(payload, session, *, user, now, user_id):
    item_id = _int_id(payload, "item_id")
    item = session.get(PantryItem, item_id)
    if not item or item.user_id != user_id:
        raise ValueError("item_id not found")
    sync_rows = session.exec(
        select(GroceryPantrySync).where(GroceryPantrySync.pantry_item_id == item_id)
    ).all()
    for row in sync_rows:
        session.delete(row)
    if sync_rows:
        session.commit()
    delete(session, item)
    return {"ok": True, "deleted_id": item_id}


def _handle_pantry_overview(payload, session, *, user, now, user_id):
    days = _clamp_int(payload.get("days"), default=7, minimum=1, maximum=365)
    overview = build_pantry_overview(session, days=days, user_id=user_id)
    return {"overview": overview.model_dump(mode="json")}


def _handle_pantry_lookup_barcode(payload, session, *, user, now, user_id):
    barcode = str(payload.get("barcode") or "").strip()
    if not barcode:
        raise ValueError("barcode is required")
    draft = _run_sync(lookup_openfoodfacts_barcode(barcode, session))
    return {"product": draft.model_dump(mode="json")}


# ── Action Catalog ────────────────────────────────────────────────────────

ACTION_CATALOG = [
    # ── Supermarket stores & connections ──
    {"action": "supermarket.list_stores", "description": "List supported supermarket stores and capabilities", "input_schema": {}, "handler": _handle_supermarket_list_stores},
    {"action": "supermarket.list_connections", "description": "List saved supermarket connections (cookie sets) across all stores. Each entry has an id, label, store, is_active flag and cookies_count.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan?"}, "handler": _handle_supermarket_list_connections},
    {"action": "supermarket.import_connection", "description": "Save a fresh cookie set for a supermarket. Set activate=true to make this connection the default consumer for the store.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan", "label": "string", "cookies": "object[]?", "credentials": "object?", "activate": "bool?", "connection_id": "int?"}, "handler": _handle_supermarket_import_connection},
    {"action": "supermarket.activate_connection", "description": "Switch the active connection for a store.", "input_schema": {"connection_id": "int"}, "handler": _handle_supermarket_activate_connection},
    {"action": "supermarket.delete_connection", "description": "Delete a saved supermarket connection.", "input_schema": {"connection_id": "int"}, "handler": _handle_supermarket_delete_connection},
    {"action": "supermarket.list_offering_contexts", "description": "List the Auchan stores selectable for an address.", "input_schema": {"zipcode": "string", "city": "string", "latitude": "float", "longitude": "float", "country": "string?"}, "handler": _handle_supermarket_list_offering_contexts},
    {"action": "supermarket.select_auchan_store", "description": "Select the Auchan store used for search.", "input_schema": {"seller_id": "string", "store_reference": "string", "store_label": "string", "channel": "string?", "location_label": "string?", "zipcode": "string?", "city": "string?", "country": "string?", "latitude": "float?", "longitude": "float?"}, "handler": _handle_supermarket_select_auchan_store},
    {"action": "supermarket.search", "description": "Search a supermarket and cache the normalized results.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan?", "queries": "string[]", "max_results": "int?", "promotions_only": "bool?"}, "handler": _handle_supermarket_search},
    # ── Supermarket Carts ──
    {"action": "supermarket.get_cart", "description": "Retrieve current contents and prices of a supermarket cart.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan", "force_sync": "bool?"}, "handler": _handle_supermarket_get_cart},
    {"action": "supermarket.list_carts", "description": "List all active supermarket shopping carts.", "input_schema": {}, "handler": _handle_supermarket_list_carts},
    {"action": "supermarket.add_cart_item", "description": "Add a product from search results to the store live cart.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan", "cache_id": "int", "quantity": "int?"}, "handler": _handle_supermarket_add_cart_item},
    {"action": "supermarket.update_cart_item", "description": "Update quantity of a line item in a store cart.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan", "item_id": "int", "quantity": "int"}, "handler": _handle_supermarket_update_cart_item},
    {"action": "supermarket.remove_cart_item", "description": "Remove a product line from a supermarket cart.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan", "item_id": "int"}, "handler": _handle_supermarket_remove_cart_item},
    {"action": "supermarket.clear_cart", "description": "Empty the shopping cart for a specific retailer.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan"}, "handler": _handle_supermarket_clear_cart},
    # ── Supermarket Drive (Store Selection, Local Staging & Sync) ──
    {"action": "supermarket.search_stores", "description": "Search physical supermarket drive stores by postal code or city across Leclerc, Carrefour, Intermarché, and Auchan.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan?", "zipcode": "string?", "city": "string?", "latitude": "float?", "longitude": "float?"}, "handler": _handle_supermarket_search_stores},
    {"action": "supermarket.set_favorite_store", "description": "Configure the user preferred drive store, pickup typology, and default optimization strategy.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan", "external_store_id": "string", "store_label": "string", "location_label": "string?", "pickup_type": "quai|spot|tape|pieton?", "optimization_strategy": "mdd|budget|bio?"}, "handler": _handle_supermarket_set_favorite_store},
    {"action": "supermarket.prepare_cart", "description": "Generate a staging draft drive shopping cart resolving unchecked grocery items to real supermarket SKUs.", "input_schema": {"store": "intermarche|carrefour|leclerc|auchan?", "optimization_strategy": "mdd|budget|bio?", "external_store_id": "string?", "item_ids": "int[]?"}, "handler": _handle_supermarket_prepare_cart},
    {"action": "supermarket.confirm_cart_sync", "description": "Push the staging cart to the retailer drive cart, marking items as in_cart=True without restocking pantry.", "input_schema": {"job_id": "int"}, "handler": _handle_supermarket_confirm_cart_sync},
    {"action": "supermarket.confirm_pickup", "description": "Confirm physical drive pickup of groceries: marks grocery items as checked=True and restocks pantry inventory.", "input_schema": {"job_id": "int"}, "handler": _handle_supermarket_confirm_pickup},
    # ── Groceries ──
    {"action": "grocery.add_item", "description": "Add an item to grocery list", "input_schema": {"name": "string", "quantity": "float?", "unit": "string?", "category": "string?", "image_url": "string?", "store_label": "string?", "external_id": "string?", "packaging": "string?", "price_text": "string?", "product_url": "string?", "priority": "int?", "note": "string?"}, "handler": _handle_grocery_add_item},
    {"action": "grocery.list_items", "description": "List grocery items", "input_schema": {"checked": "bool?", "limit": "int?"}, "handler": _handle_grocery_list_items},
    {"action": "grocery.update_item", "description": "Update a grocery item", "input_schema": {"item_id": "int", "quantity": "float?", "unit": "string?", "category": "string?", "checked": "bool?", "priority": "int?", "note": "string?"}, "handler": _handle_grocery_update_item},
    {"action": "grocery.check_item", "description": "Mark grocery item checked or unchecked", "input_schema": {"item_id": "int", "checked": "bool?"}, "handler": _handle_grocery_check_item},
    {"action": "grocery.delete_item", "description": "Delete a grocery item", "input_schema": {"item_id": "int"}, "handler": _handle_grocery_delete_item},
    # ── Recipes ──
    {"action": "recipe.add", "description": "Create a recipe with optional ingredients", "input_schema": {"name": "string", "description": "string?", "instructions": "string", "steps": "string[]?", "utensils": "string[]?", "prep_minutes": "int?", "cook_minutes": "int?", "servings": "int?", "tags": "string[]?", "source_url": "string?", "source_platform": "string?", "source_title": "string?", "source_description": "string?", "source_transcript": "string?", "ingredients": "[{name, quantity, unit, note, category, cache_id}]?"}, "handler": _handle_recipe_add},
    {"action": "recipe.list", "description": "List recipes", "input_schema": {"limit": "int?"}, "handler": _handle_recipe_list},
    {"action": "recipe.get", "description": "Get one recipe by id", "input_schema": {"recipe_id": "int"}, "handler": _handle_recipe_get},
    {"action": "recipe.update", "description": "Update a recipe", "input_schema": {"recipe_id": "int", "name": "string?", "description": "string?", "instructions": "string?", "steps": "string[]?", "utensils": "string[]?", "prep_minutes": "int?", "cook_minutes": "int?", "servings": "int?", "tags": "string[]?", "source_url": "string?", "source_platform": "string?", "source_title": "string?", "source_description": "string?", "source_transcript": "string?", "ingredients": "[{name, quantity, unit, note, category, cache_id}]?"}, "handler": _handle_recipe_update},
    {"action": "recipe.confirm_cooked", "description": "Confirm a recipe was cooked and consume pantry ingredients", "input_schema": {"recipe_id": "int", "servings_override": "int?", "note": "string?"}, "handler": _handle_recipe_confirm_cooked},
    {"action": "recipe.unconfirm_cooked", "description": "Undo a recipe-level cooked confirmation and restore pantry stock", "input_schema": {"recipe_id": "int"}, "handler": _handle_recipe_unconfirm_cooked},
    {"action": "recipe.delete", "description": "Delete a recipe and its dependent recipe ingredients / meal plans", "input_schema": {"recipe_id": "int"}, "handler": _handle_recipe_delete},
    # ── Meal Plans ──
    {"action": "meal_plan.add", "description": "Plan a recipe at a specific datetime or slot", "input_schema": {"planned_at": "datetime?", "planned_for": "YYYY-MM-DD?", "slot": "breakfast|lunch|dinner?", "recipe_id": "int", "servings_override": "int?", "note": "string?", "auto_add_missing_ingredients": "bool?"}, "handler": _handle_meal_plan_add},
    {"action": "meal_plan.log_cooked", "description": "Log a recipe as cooked without pre-planning", "input_schema": {"recipe_id": "int", "cooked_at": "datetime?", "servings_override": "int?", "note": "string?"}, "handler": _handle_meal_plan_log_cooked},
    {"action": "meal_plan.list", "description": "List meal plans", "input_schema": {"date_from": "YYYY-MM-DD?", "date_to": "YYYY-MM-DD?", "slot": "breakfast|lunch|dinner?", "limit": "int?"}, "handler": _handle_meal_plan_list},
    {"action": "meal_plan.update", "description": "Update one meal plan", "input_schema": {"meal_plan_id": "int", "planned_at": "datetime?", "planned_for": "YYYY-MM-DD?", "slot": "breakfast|lunch|dinner?", "recipe_id": "int?", "servings_override": "int?", "note": "string?", "auto_add_missing_ingredients": "bool?"}, "handler": _handle_meal_plan_update},
    {"action": "meal_plan.delete", "description": "Delete one meal plan", "input_schema": {"meal_plan_id": "int"}, "handler": _handle_meal_plan_delete},
    {"action": "meal_plan.sync_groceries", "description": "Sync missing ingredients to grocery list for one meal plan", "input_schema": {"meal_plan_id": "int"}, "handler": _handle_meal_plan_sync_groceries},
    {"action": "meal_plan.confirm_cooked", "description": "Confirm meal was cooked and consume pantry ingredients", "input_schema": {"meal_plan_id": "int", "note": "string?"}, "handler": _handle_meal_plan_confirm_cooked},
    {"action": "meal_plan.unconfirm_cooked", "description": "Undo cooked confirmation and restore pantry", "input_schema": {"meal_plan_id": "int"}, "handler": _handle_meal_plan_unconfirm_cooked},
    # ── Pantry ──
    {"action": "pantry.add_item", "description": "Add pantry item", "input_schema": {"name": "string", "quantity": "float?", "unit": "string?", "category": "string?", "min_quantity": "float?", "expires_at": "YYYY-MM-DD?", "location": "string?", "note": "string?"}, "handler": _handle_pantry_add_item},
    {"action": "pantry.list_items", "description": "List pantry items", "input_schema": {"low_stock_only": "bool?", "expiring_in_days": "int?", "limit": "int?"}, "handler": _handle_pantry_list_items},
    {"action": "pantry.update_item", "description": "Update pantry item", "input_schema": {"item_id": "int", "quantity": "float?", "unit": "string?", "category": "string?", "min_quantity": "float?", "expires_at": "YYYY-MM-DD?", "location": "string?", "note": "string?"}, "handler": _handle_pantry_update_item},
    {"action": "pantry.consume_item", "description": "Decrease pantry item quantity", "input_schema": {"item_id": "int", "amount": "float"}, "handler": _handle_pantry_consume_item},
    {"action": "pantry.delete_item", "description": "Delete pantry item", "input_schema": {"item_id": "int"}, "handler": _handle_pantry_delete_item},
    {"action": "pantry.overview", "description": "Get pantry overview", "input_schema": {"days": "int?"}, "handler": _handle_pantry_overview},
    {"action": "pantry.lookup_barcode", "description": "Lookup product details by barcode via Open Food Facts", "input_schema": {"barcode": "string"}, "handler": _handle_pantry_lookup_barcode},
]


def _action_registry() -> dict[str, dict]:
    """Action name -> catalog entry (the catalog IS the dispatch)."""
    return {entry["action"]: entry for entry in ACTION_CATALOG}


_ACTION_REGISTRY = _action_registry()


def action_catalog_manifest() -> list[dict]:
    """ACTION_CATALOG without the dispatch-only `handler` key, for the manifest."""
    return [
        {key: value for key, value in entry.items() if key != "handler"}
        for entry in ACTION_CATALOG
    ]


def execute_action(
    action: str,
    payload: dict,
    session,
    *,
    user: User | None = None,
) -> dict:
    entry = _ACTION_REGISTRY.get(action)
    if entry is None:
        raise ValueError(f"Unknown action: {action}")
    now = datetime.now(timezone.utc)
    user_id = user.id if user is not None else None
    return entry["handler"](payload, session, user=user, now=now, user_id=user_id)
