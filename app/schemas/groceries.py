from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GroceryItemCreate(BaseModel):
    name: str
    quantity: float = Field(default=1, ge=0)
    unit: str = "item"
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    # When set, store metadata (store_label/external_id/price_text/product_url)
    # is resolved server-side from this SupermarketSearchCache row and any
    # client-supplied value for those fields is ignored.
    cache_id: int | None = None
    priority: int = 3
    note: str | None = None


class GroceryItemUpdate(BaseModel):
    name: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    unit: str | None = None
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    cache_id: int | None = None
    checked: bool | None = None
    priority: int | None = None
    note: str | None = None


class GroceryItemRead(BaseModel):
    id: int
    name: str
    quantity: float
    unit: str
    category: str | None
    image_url: str | None
    store_label: str | None
    external_id: str | None
    packaging: str | None
    price_text: str | None
    product_url: str | None
    checked: bool
    priority: int
    note: str | None
    created_at: datetime
    updated_at: datetime
