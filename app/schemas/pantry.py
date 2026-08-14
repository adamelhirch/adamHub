from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class PantryItemCreate(BaseModel):
    name: str
    quantity: float = Field(default=0, ge=0)
    unit: str = "item"
    category: str | None = None
    image_url: str | None = None
    store_label: str | None = None
    external_id: str | None = None
    packaging: str | None = None
    price_text: str | None = None
    product_url: str | None = None
    cache_id: int | None = None
    min_quantity: float = Field(default=0, ge=0)
    expires_at: date | None = None
    location: str | None = None
    note: str | None = None


class PantryItemUpdate(BaseModel):
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
    min_quantity: float | None = Field(default=None, ge=0)
    expires_at: date | None = None
    location: str | None = None
    note: str | None = None


class PantryConsume(BaseModel):
    amount: float = Field(gt=0)


class PantryItemRead(BaseModel):
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
    min_quantity: float
    expires_at: date | None
    location: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class PantryOverview(BaseModel):
    total_items: int
    low_stock_items: int
    expiring_within_7_days: int
