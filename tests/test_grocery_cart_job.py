from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app.models import (
    GroceryItem,
    GroceryToCartJob,
    MatchedCartItem,
    SupermarketMapping,
    SupermarketSearchCache,
    SupermarketStore,
    SupermarketTargetType,
    UserStorePreference,
)
from app.services.supermarket.cart_job_service import CartJobService
from app.services.supermarket.cart_matcher import CartMatcherService
from tests.conftest import register_user


def _seed_cache(
    session: Session,
    *,
    store: SupermarketStore = SupermarketStore.LECLERC,
    name: str,
    brand: str | None = None,
    query: str = "lait",
    price_amount: float = 1.20,
    packaging: str = "1 L",
    external_id: str = "sku-1",
) -> SupermarketSearchCache:
    now = datetime.now(UTC)
    row = SupermarketSearchCache(
        store=store,
        query=query,
        external_id=external_id,
        name=name,
        brand=brand,
        packaging=packaging,
        price_amount=price_amount,
        price_text=f"{price_amount:.2f} €",
        image_url="https://img.test/p.png",
        product_url="https://store.test/p",
        fetched_at=now,
        expires_at=now + timedelta(days=2),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_cart_matcher_strategies(test_engine):
    with Session(test_engine) as session:
        # Seed cache items for Leclerc
        p_mdd = _seed_cache(
            session,
            store=SupermarketStore.LECLERC,
            name="Lait demi-écrémé Marque Repère",
            brand="Marque Repère",
            query="lait",
            price_amount=1.15,
            external_id="sku-mdd",
        )
        p_budget = _seed_cache(
            session,
            store=SupermarketStore.LECLERC,
            name="Lait premier prix Eco+",
            brand="Eco+",
            query="lait",
            price_amount=0.99,
            external_id="sku-budget",
        )
        p_bio = _seed_cache(
            session,
            store=SupermarketStore.LECLERC,
            name="Lait Bio Village biologique",
            brand="Bio Village",
            query="lait",
            price_amount=1.55,
            external_id="sku-bio",
        )

        item = GroceryItem(name="Lait demi-écrémé", quantity=2, unit="L")
        session.add(item)
        session.commit()
        session.refresh(item)

        # 1. MDD strategy
        matched_mdd = CartMatcherService.match_grocery_item(
            session, item, store=SupermarketStore.LECLERC, strategy="mdd", user_id=1
        )
        assert matched_mdd is not None
        assert matched_mdd.cache_id == p_mdd.id
        assert matched_mdd.match_type == "mdd"

        # 2. Budget strategy
        matched_budget = CartMatcherService.match_grocery_item(
            session, item, store=SupermarketStore.LECLERC, strategy="budget", user_id=1
        )
        assert matched_budget is not None
        assert matched_budget.cache_id == p_budget.id
        assert matched_budget.match_type == "budget"

        # 3. Bio strategy
        matched_bio = CartMatcherService.match_grocery_item(
            session, item, store=SupermarketStore.LECLERC, strategy="bio", user_id=1
        )
        assert matched_bio is not None
        assert matched_bio.cache_id == p_bio.id
        assert matched_bio.match_type == "bio"


def test_cart_matcher_prioritizes_history(test_engine):
    with Session(test_engine) as session:
        p_custom = _seed_cache(
            session,
            store=SupermarketStore.LECLERC,
            name="Lait Spécial Délices",
            brand="Grandlait",
            query="lait",
            price_amount=1.80,
            external_id="sku-custom",
        )
        item = GroceryItem(name="Lait favori", quantity=1, unit="L")
        session.add(item)
        session.commit()
        session.refresh(item)

        # Add prior job and matched item for user 42
        prior_job = GroceryToCartJob(
            user_id=42,
            store=SupermarketStore.LECLERC,
            external_store_id="0123",
            status="completed",
        )
        session.add(prior_job)
        session.commit()
        session.refresh(prior_job)

        prior_item = MatchedCartItem(
            job_id=prior_job.id,
            cache_id=p_custom.id,
            external_id=p_custom.external_id,
            name="Lait favori",
            quantity=1,
            unit_price_cents=180,
            total_price_cents=180,
            status="synced",
        )
        session.add(prior_item)
        session.commit()

        matched = CartMatcherService.match_grocery_item(
            session, item, store=SupermarketStore.LECLERC, strategy="mdd", user_id=42
        )
        assert matched is not None
        assert matched.cache_id == p_custom.id
        assert matched.match_type == "exact_history"


def test_cart_job_creation_and_api_flow(client, test_engine):
    user = register_user(client, "cart-job-user@adamelhirch.com")

    # Set up user store preference
    client.put(
        "/api/v1/supermarket/stores/preferences/leclerc",
        headers=user["headers"],
        json={
            "external_store_id": "0123",
            "store_label": "E.Leclerc Drive Blagnac",
            "pickup_type": "quai",
            "optimization_strategy": "mdd",
        },
    )

    with Session(test_engine) as session:
        # Create 2 grocery items for this user
        item1 = GroceryItem(user_id=user["user"]["id"], name="Beurre doux", quantity=1, unit="item")
        item2 = GroceryItem(user_id=user["user"]["id"], name="Oeufs frais", quantity=6, unit="item")
        session.add_all([item1, item2])
        session.commit()
        session.refresh(item1)
        session.refresh(item2)

        _seed_cache(
            session,
            store=SupermarketStore.LECLERC,
            name="Beurre doux Marque Repère 250g",
            brand="Marque Repère",
            query="beurre doux",
            price_amount=2.10,
            packaging="250g",
        )
        _seed_cache(
            session,
            store=SupermarketStore.LECLERC,
            name="Oeufs frais plein air x6",
            brand="Marque Repère",
            query="oeufs frais",
            price_amount=2.40,
            packaging="boîte de 6",
        )

    # Trigger draft cart creation
    res = client.post(
        "/api/v1/supermarket/cart/jobs",
        headers=user["headers"],
        json={
            "store": "leclerc",
            "optimization_strategy": "mdd",
        },
    )
    assert res.status_code == 201, res.text
    job_data = res.json()
    assert job_data["store"] == "leclerc"
    assert job_data["status"] == "reviewing"
    assert job_data["items_count"] == 2
    assert job_data["matched_count"] == 2
    assert job_data["estimated_total_cents"] == 450  # 210 + 240
    assert len(job_data["items"]) == 2

    job_id = job_data["id"]

    # Read the job back
    read_res = client.get(f"/api/v1/supermarket/cart/jobs/{job_id}", headers=user["headers"])
    assert read_res.status_code == 200
    assert read_res.json()["id"] == job_id


def test_cart_job_cross_user_isolation(client, test_engine):
    user_a = register_user(client, "cart-job-a@adamelhirch.com")
    user_b = register_user(client, "cart-job-b@adamelhirch.com")

    with Session(test_engine) as session:
        job = GroceryToCartJob(
            user_id=user_a["user"]["id"],
            store=SupermarketStore.LECLERC,
            external_store_id="0123",
            status="reviewing",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id = job.id

    # User B tries to read User A's job -> 404
    b_res = client.get(f"/api/v1/supermarket/cart/jobs/{job_id}", headers=user_b["headers"])
    assert b_res.status_code == 404


def test_cart_matcher_rejects_irrelevant_culinary_adjective_matches(test_engine):
    with Session(test_engine) as session:
        # Cache only contains whole milk and fresh eggs
        p_milk = _seed_cache(
            session,
            store=SupermarketStore.INTERMARCHE,
            name="Grandlait frais - Lait frais de Montagne entier",
            brand="Grandlait",
            query="lait",
            price_amount=1.61,
            external_id="sku-milk",
        )
        p_eggs = _seed_cache(
            session,
            store=SupermarketStore.INTERMARCHE,
            name="œufs frais de poules élevées en plein air",
            brand="Volaé",
            query="oeufs",
            price_amount=2.92,
            external_id="sku-eggs",
        )

        # User wants "crème liquide entière"
        item_cream = GroceryItem(name="crème liquide entière", quantity=1, unit="brique")
        # User wants "saumon frais sans peau"
        item_salmon = GroceryItem(name="saumon frais sans peau", quantity=250, unit="g")
        session.add(item_cream)
        session.add(item_salmon)
        session.commit()

        # Matcher MUST NOT match milk for cream simply because "entier" is in milk!
        matched_cream = CartMatcherService.match_grocery_item(
            session, item_cream, store=SupermarketStore.INTERMARCHE, strategy="mdd", user_id=1
        )
        assert matched_cream is None, "Whole milk must not match cream!"

        # Matcher MUST NOT match eggs for salmon simply because "frais" is in eggs!
        matched_salmon = CartMatcherService.match_grocery_item(
            session, item_salmon, store=SupermarketStore.INTERMARCHE, strategy="mdd", user_id=1
        )
        assert matched_salmon is None, "Eggs must not match salmon!"


def test_cart_matcher_rejects_category_and_substring_incompatibilities(test_engine):
    with Session(test_engine) as session:
        p_broth = _seed_cache(
            session,
            store=SupermarketStore.CARREFOUR,
            name="Bouillon Déshydraté de Volaille MAGGI",
            brand="MAGGI",
            query="bouillon",
            price_amount=1.89,
            external_id="sku-broth",
        )
        p_butter = _seed_cache(
            session,
            store=SupermarketStore.CARREFOUR,
            name="Beurre moulé demi-sel crème française",
            brand="Pâturages",
            query="beurre",
            price_amount=5.05,
            external_id="sku-butter",
        )
        p_milk = _seed_cache(
            session,
            store=SupermarketStore.CARREFOUR,
            name="Lait Demi-Ecrémé CARREFOUR CLASSIC'",
            brand="Carrefour Classic'",
            query="lait",
            price_amount=1.08,
            external_id="sku-cow-milk",
        )
        p_tomato = _seed_cache(
            session,
            store=SupermarketStore.CARREFOUR,
            name="Tomates RONDES",
            brand="Primeur",
            query="tomate",
            price_amount=0.55,
            external_id="sku-fresh-tomatoes",
        )
        p_veggie_slices = _seed_cache(
            session,
            store=SupermarketStore.CARREFOUR,
            name="Tranches Végé aux Lentilles Corail",
            brand="Fleury Michon",
            query="lentilles",
            price_amount=2.60,
            external_id="sku-slices",
        )

        item_garlic = GroceryItem(name="Ail", quantity=1, unit="item")
        item_salt = GroceryItem(name="Sel", quantity=1, unit="pincée")
        item_coco = GroceryItem(name="Lait de coco", quantity=20, unit="cl")
        item_paste = GroceryItem(name="Concentré de tomate", quantity=1, unit="c. à soupe")
        item_lentils = GroceryItem(name="Lentilles corail", quantity=150, unit="g")

        session.add_all([item_garlic, item_salt, item_coco, item_paste, item_lentils])
        session.commit()

        # 1. Garlic must not match poultry broth (vol-aille)
        m_garlic = CartMatcherService.match_grocery_item(
            session, item_garlic, store=SupermarketStore.CARREFOUR, strategy="budget"
        )
        assert m_garlic is None, "Garlic must not match chicken broth via substring 'ail' in 'volaille'!"

        # 2. Salt must not match 5€ salted butter
        m_salt = CartMatcherService.match_grocery_item(
            session, item_salt, store=SupermarketStore.CARREFOUR, strategy="budget"
        )
        assert m_salt is None, "Salt must not match butter with incompatible head noun!"

        # 3. Coconut milk must not match cow milk
        m_coco = CartMatcherService.match_grocery_item(
            session, item_coco, store=SupermarketStore.CARREFOUR, strategy="budget"
        )
        assert m_coco is None, "Coconut milk must require qualifier 'coco'!"

        # 4. Tomato paste must not match fresh round tomatoes
        m_paste = CartMatcherService.match_grocery_item(
            session, item_paste, store=SupermarketStore.CARREFOUR, strategy="budget"
        )
        assert m_paste is None, "Tomato paste must require qualifier 'concentré'!"

        # 5. Raw coral lentils must not match processed veggie cold cut slices
        m_lentils = CartMatcherService.match_grocery_item(
            session, item_lentils, store=SupermarketStore.CARREFOUR, strategy="budget"
        )
        assert m_lentils is None, "Lentils must not match processed veggie slices!"


