from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models import SupermarketStore, SupermarketTargetType


class SupermarketSearchRequest(BaseModel):
    store: SupermarketStore = SupermarketStore.INTERMARCHE
    queries: list[str] = Field(default_factory=list, min_length=1, max_length=10)
    max_results: int = Field(default=10, ge=1, le=200)
    promotions_only: bool = False
    sort_by: str | None = Field(default=None, description="One of: 'price_asc', 'price_desc'.")


class SupermarketSearchResult(BaseModel):
    cache_id: int
    store: SupermarketStore
    query: str
    external_id: str | None
    name: str
    brand: str | None
    category: str | None = None
    packaging: str | None
    price_amount: float | None
    price_text: str | None
    image_url: str | None
    product_url: str | None
    fetched_at: datetime
    expires_at: datetime


class SupermarketStoreRead(BaseModel):
    key: SupermarketStore
    label: str
    supports_search: bool = True
    supports_mapping: bool = True
    supports_cart_automation: bool = False


class UbereatsAddressUpdate(BaseModel):
    title: str
    subtitle: str | None = None
    formatted_address: str | None = None
    latitude: float
    longitude: float
    reference: str | None = None
    reference_type: str = "GOOGLE_PLACES"


class UbereatsGeocodeResult(BaseModel):
    title: str
    subtitle: str | None = None
    formatted_address: str
    latitude: float
    longitude: float
    reference: str | None = None
    reference_type: str = "OSM_NOMINATIM"


class UbereatsAddressCreate(BaseModel):
    label: str
    formatted_address: str
    subtitle: str | None = None
    latitude: float
    longitude: float
    reference: str | None = None
    reference_type: str = "OSM_NOMINATIM"
    activate: bool = False


class UbereatsAddressRead(BaseModel):
    id: int
    label: str
    formatted_address: str
    subtitle: str | None
    latitude: float
    longitude: float
    reference: str | None
    reference_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UbereatsCartAddRequest(BaseModel):
    cache_id: int
    quantity: int = Field(default=1, ge=1, le=99)


class UbereatsCartItem(BaseModel):
    item_uuid: str
    cart_item_uuid: str
    title: str
    quantity: int
    price_cents: int | None = None
    image_url: str | None = None


class UbereatsCartRead(BaseModel):
    draft_order_uuid: str | None
    cart_uuid: str | None
    store_uuid: str | None
    items: list[UbereatsCartItem]


class UbereatsCartSummaryEntry(BaseModel):
    draft_order_uuid: str | None
    title: str | None
    subtotal_text: str | None
    item_count: int | None
    store_image_urls: list[str] = Field(default_factory=list)
    details: UbereatsCartRead | None = None


class UbereatsCartSummary(BaseModel):
    carts: list[UbereatsCartSummaryEntry]
    focused: UbereatsCartRead | None = None


class UbereatsPastOrder(BaseModel):
    uuid: str
    store_title: str | None
    store_image_url: str | None
    completed_at: str | None
    is_completed: bool
    is_cancelled: bool
    num_items: int
    total_quantity: int
    total_text: str | None


class UbereatsImportRequest(BaseModel):
    tracking_url_or_uuid: str = Field(min_length=4, max_length=400)


class UbereatsImportedItem(BaseModel):
    name: str
    quantity: float
    external_id: str | None
    price_text: str | None
    created: bool


class UbereatsImportResult(BaseModel):
    order_uuid: str
    store_label: str | None = None
    items_imported: int
    items_updated: int
    items: list[UbereatsImportedItem]


class SupermarketConnectionRead(BaseModel):
    id: int
    store: SupermarketStore
    label: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime
    cookies_count: int


class SupermarketConnectionImport(BaseModel):
    store: SupermarketStore
    label: str
    cookies: list[dict]
    activate: bool = True
    connection_id: int | None = None


class UbereatsLocationRead(BaseModel):
    label: str | None
    title: str | None
    formatted_address: str | None
    latitude: float | None
    longitude: float | None


class UbereatsStoreOption(BaseModel):
    uuid: str
    name: str
    subtitle: str | None = None
    address: str | None = None
    rating: float | None = None
    image_url: str | None = None


class UbereatsStoreSelectionRequest(BaseModel):
    external_store_id: str
    store_label: str
    location_label: str | None = None


class UbereatsStoreSelectionRead(BaseModel):
    external_store_id: str
    store_label: str
    location_label: str | None
    updated_at: datetime


class SupermarketMappingCreate(BaseModel):
    cache_id: int
    store: SupermarketStore = SupermarketStore.INTERMARCHE
    # Snapshot fields are resolved server-side from the cache row; kept optional
    # for backward compatibility with clients that still send them.
    external_id: str | None = None
    store_label: str | None = None
    name_snapshot: str | None = None
    category_snapshot: str | None = None
    packaging_snapshot: str | None = None
    price_snapshot: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    last_verified_at: datetime | None = None


class SupermarketMappingRead(BaseModel):
    id: int
    target_type: SupermarketTargetType
    target_id: int
    store: SupermarketStore
    external_id: str
    store_label: str
    name_snapshot: str
    category_snapshot: str | None
    packaging_snapshot: str | None
    price_snapshot: str | None
    product_url: str | None
    image_url: str | None
    last_verified_at: datetime
    active: bool
    created_at: datetime
    updated_at: datetime
