from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Unités de Mesure
# ---------------------------------------------------------------------------

class UnitOfMeasureCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    label: str = Field(min_length=1, max_length=50)
    magnitude_type: str = Field(default="mass", max_length=30)
    conversion_factor_to_base: float = Field(default=1.0, gt=0)


class UnitOfMeasureRead(BaseModel):
    code: str
    label: str
    magnitude_type: str
    conversion_factor_to_base: float


# ---------------------------------------------------------------------------
# 2. Ingrédients Canoniques
# ---------------------------------------------------------------------------

class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category: str | None = Field(default=None, max_length=50)
    default_unit_code: str | None = None


class IngredientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    category: str | None = None
    default_unit_code: str | None = None


class IngredientRead(BaseModel):
    id: int
    name: str
    category: str | None = None
    default_unit_code: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# 3. Ustensiles
# ---------------------------------------------------------------------------

class UtensilCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class UtensilRead(BaseModel):
    id: int
    name: str
    created_at: datetime


# ---------------------------------------------------------------------------
# 4. Tags
# ---------------------------------------------------------------------------

class TagCreate(BaseModel):
    label: str = Field(min_length=1, max_length=50)


class TagRead(BaseModel):
    id: int
    label: str
    created_at: datetime


# ---------------------------------------------------------------------------
# 5. Régimes Alimentaires (Dietary Preferences)
# ---------------------------------------------------------------------------

class DietaryPreferenceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class DietaryPreferenceRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    created_at: datetime


class UserDietaryPreferencesSet(BaseModel):
    dietary_preference_ids: list[int] = Field(default_factory=list)
