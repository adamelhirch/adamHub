from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import Session, select

from app.models.entities import OpenFoodFactsCache
from app.services.openfoodfacts import clean_openfoodfacts_product, lookup_openfoodfacts_barcode


def test_clean_openfoodfacts_product_pasta_strips_brand_and_preserves_variety():
    raw = {
        "product_name_fr": "Carrefour Extra Penne Rigate 500g",
        "brands": "Carrefour Extra",
        "quantity": "500 g",
        "product_quantity": 500,
        "product_quantity_unit": "g",
        "categories_tags": ["en:plant-based-foods", "en:cereals-and-potatoes", "en:pastas"],
        "nutriscore_grade": "a",
        "image_front_url": "https://images.openfoodfacts.org/front.jpg",
    }
    draft = clean_openfoodfacts_product(raw, "3560070557451")

    assert draft.found is True
    assert draft.barcode == "3560070557451"
    assert draft.brand == "Carrefour Extra"
    assert "penne" in draft.suggested_name.lower()
    assert "carrefour" not in draft.suggested_name.lower()
    assert draft.quantity == 500.0
    assert draft.unit == "g"
    assert draft.category == "Épicerie"
    assert draft.location == "Placard"
    assert draft.nutriscore == "a"
    assert "expires_at" in draft.missing_fields


def test_clean_openfoodfacts_product_trombonnes():
    raw = {
        "product_name_fr": "Pâtes Trombonnes",
        "brands": "Barilla",
        "quantity": "250g",
        "categories_tags": ["en:pastas"],
    }
    draft = clean_openfoodfacts_product(raw, "1234567890123")
    assert "trombonne" in draft.suggested_name.lower()
    assert draft.quantity == 250.0
    assert draft.unit == "g"


def test_clean_openfoodfacts_product_fish():
    raw = {
        "product_name_fr": "2 Pavés de Saumon frais avec peau",
        "brands": "Simpl",
        "quantity": "250 g",
        "categories_tags": ["en:seafood", "en:fishes", "en:salmons"],
    }
    draft = clean_openfoodfacts_product(raw, "9876543210987")
    assert "saumon" in draft.suggested_name.lower()
    assert draft.quantity == 250.0
    assert draft.unit == "g"
    assert draft.category == "Poisson"
    assert draft.location == "Réfrigérateur"


def test_barcode_endpoint_with_cache(client, auth_headers, test_engine):
    barcode = "3560070557451"
    now = datetime.now(UTC)

    # Insert cached product into DB
    with Session(test_engine) as session:
        cache_row = OpenFoodFactsCache(
            barcode=barcode,
            raw_payload={
                "product_name_fr": "Carrefour Extra Penne Rigate 500g",
                "brands": "Carrefour Extra",
                "quantity": "500 g",
                "categories_tags": ["en:pastas"],
            },
            product_name="Carrefour Extra Penne Rigate 500g",
            brand="Carrefour Extra",
            quantity_text="500 g",
            expires_at=now + timedelta(days=10),
        )
        session.add(cache_row)
        session.commit()

    res = client.get(f"/api/v1/pantry/barcode/{barcode}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["found"] is True
    assert data["barcode"] == barcode
    assert "penne" in data["suggested_name"].lower()
    assert data["quantity"] == 500.0
    assert data["unit"] == "g"


def test_skill_action_pantry_lookup_barcode(client, auth_headers, test_engine):
    barcode = "3560070557451"
    now = datetime.now(UTC)

    with Session(test_engine) as session:
        cache_row = OpenFoodFactsCache(
            barcode=barcode,
            raw_payload={
                "product_name_fr": "Carrefour Extra Penne Rigate 500g",
                "brands": "Carrefour Extra",
                "quantity": "500 g",
                "categories_tags": ["en:pastas"],
            },
            product_name="Carrefour Extra Penne Rigate 500g",
            brand="Carrefour Extra",
            quantity_text="500 g",
            expires_at=now + timedelta(days=10),
        )
        session.add(cache_row)
        session.commit()

    res = client.post(
        "/api/v1/skill/execute",
        headers=auth_headers,
        json={"action": "pantry.lookup_barcode", "input": {"barcode": barcode}},
    )
    assert res.status_code == 200
    data = res.json()["data"]["product"]
    assert data["found"] is True
    assert data["barcode"] == barcode
    assert "penne" in data["suggested_name"].lower()
    assert data["quantity"] == 500.0
    assert data["unit"] == "g"

