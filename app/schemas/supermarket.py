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


class SupermarketConnectionRead(BaseModel):
    id: int
    store: SupermarketStore
    label: str
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime
    cookies_count: int


class SupermarketCredentials(BaseModel):
    """Best-effort login/password for a store that supports programmatic login.

    Encrypted at rest inside the same `cookies_encrypted` container as cookie
    sets. This is a fallback only: the browser extension (cookies) remains the
    reliable path, and programmatic login is not wired to any scraper yet.
    """

    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class SupermarketConnectionImport(BaseModel):
    store: SupermarketStore
    label: str
    cookies: list[dict] = Field(default_factory=list)
    credentials: SupermarketCredentials | None = None
    activate: bool = True
    connection_id: int | None = None


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
    cache_id: int | None = None
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
