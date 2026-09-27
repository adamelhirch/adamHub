from __future__ import annotations

from datetime import UTC, datetime, timedelta
import pytest
from sqlmodel import Session, select

from app.models import (
    GroceryItem,
    SupermarketSearchCache,
    SupermarketStore,
)
from app.services.supermarket.cart_matcher import CartMatcherService
from app.services.supermarket.culinary_guardrails import (
    is_budget_first_price,
    is_disqualified_by_culinary_guardrails,
)


@pytest.fixture
def session(test_engine):
    with Session(test_engine) as s:
        yield s


# ─────────────────────────────────────────────────────────────────────────────
# 1. Tests unitaires des filtres culinaires anti-aberrations
# ─────────────────────────────────────────────────────────────────────────────

def test_guardrails_disqualify_processed_lentil_substitutes():
    """Lentilles brutes must reject cold cuts, soups, salads, dips & processed dishes."""
    head_noun = "lentilles"
    search_terms = ["lentilles", "corail"]

    # Faux-amis et aberrations constatées par l'utilisateur
    bad_candidates = [
        ("Tranches végétales aux lentilles Fleury Michon", "Fleury Michon"),
        ("Salade de lentilles corail et riz rouge", "Bonduelle"),
        ("Houmous lentilles corail gingembre curcuma", "Atelier Blini"),
        ("Velouté de lentilles corail coco curry bio 1L", "Knorr"),
        ("Boulettes végétales aux lentilles et carottes", "Herta"),
        ("Allumettes végétales saveur fumée", "La Vie"),
        ("Plat cuisiné Dahl de lentilles en barquette", "Marie"),
        ("Chips de lentilles pointe de sel", "Lay's"),
    ]

    for name, brand in bad_candidates:
        disq, reason = is_disqualified_by_culinary_guardrails(head_noun, search_terms, name, brand)
        assert disq is True, f"'{name}' ({brand}) aurait dû être rejeté ! Raison: {reason}"

    # Vraies lentilles brutes : DOIVENT passer
    valid_candidates = [
        ("Lentilles Corail CARREFOUR CLASSIC' 500g", "CARREFOUR CLASSIC'"),
        ("Lentilles Corail Bio 500g", "CARREFOUR BIO"),
        ("Lentilles corail en sachet SIMPL", "SIMPL"),
        ("Lentilles corail Saint Eloi 500g", "Saint Eloi"),
    ]

    for name, brand in valid_candidates:
        disq, reason = is_disqualified_by_culinary_guardrails(head_noun, search_terms, name, brand)
        assert disq is False, f"'{name}' ({brand}) aurait dû être accepté ! Rejeté avec: {reason}"


def test_guardrails_disqualify_processed_chicken_and_meat():
    """Poulet / volaille brute must reject nuggets, cordons bleus, chips & sandwiches."""
    head_noun = "poulet"
    search_terms = ["poulet", "filet"]

    bad_candidates = [
        ("Nuggets de poulet panés x20", "Maître CoQ"),
        ("Cordon bleu de volaille au fromage", "Père Dodu"),
        ("Croquettes de poulet croustillantes", "Le Gaulois"),
        ("Sandwich triangle club poulet rôti", "Daunat"),
        ("Salade Caesar poulet émincé", "Sodebo"),
        ("Bouillon déshydraté de volaille", "Maggi"),
        ("Chips goût poulet braisé ondulées", "Brets"),
    ]

    for name, brand in bad_candidates:
        disq, reason = is_disqualified_by_culinary_guardrails(head_noun, search_terms, name, brand)
        assert disq is True, f"'{name}' ({brand}) aurait dû être rejeté !"

    # Vrai poulet brut
    valid_candidates = [
        ("Filets de poulet jaune x2 250g", "Volaé"),
        ("Blancs de poulet français Pouce", "Pouce"),
        ("Filet de poulet fermier Label Rouge", "Carrefour Classic'"),
    ]

    for name, brand in valid_candidates:
        disq, reason = is_disqualified_by_culinary_guardrails(head_noun, search_terms, name, brand)
        assert disq is False, f"'{name}' aurait dû être accepté !"


def test_guardrails_disqualify_processed_salmon():
    """Saumon brut pour cuisson must reject pizzas, quiches, lasagnes & rillettes."""
    head_noun = "saumon"
    search_terms = ["saumon"]

    bad_candidates = [
        ("Lasagnes au saumon et épinards 400g", "Marie"),
        ("Pizza saumon crème fraîche ciboulette", "Buitoni"),
        ("Quiche au saumon et poireaux", "Monique Ranou"),
        ("Rillettes de saumon de l'Atlantique", "Capitaine Cook"),
        ("Pâtes au saumon micro-ondables", "Fleury Michon"),
    ]

    for name, brand in bad_candidates:
        disq, reason = is_disqualified_by_culinary_guardrails(head_noun, search_terms, name, brand)
        assert disq is True, f"'{name}' aurait dû être rejeté !"

    valid_candidates = [
        ("2 Pavés de saumon frais avec peau 280g", "Filière Qualité Carrefour"),
        ("Pavés de saumon surgelés x2 250g", "Odyssée"),
        ("Dos de saumon frais", "Pêche Océan"),
    ]

    for name, brand in valid_candidates:
        disq, reason = is_disqualified_by_culinary_guardrails(head_noun, search_terms, name, brand)
        assert disq is False, f"'{name}' aurait dû être accepté !"


def test_guardrails_enforce_essential_qualifiers():
    """Coco, corail, concentré must be enforced to avoid false matches."""
    # Lait de coco vs Lait de vache
    disq_cow, _ = is_disqualified_by_culinary_guardrails(
        "lait", ["lait", "coco"], "Lait demi-écrémé UHT 1L", "Candia"
    )
    assert disq_cow is True, "Lait de vache ne doit pas matcher 'lait de coco' !"

    disq_coco, _ = is_disqualified_by_culinary_guardrails(
        "lait", ["lait", "coco"], "Lait de coco fluide 200ml", "Kara"
    )
    assert disq_coco is False

    # Concentré de tomate vs Sauce tomate bolognaise
    disq_bolo, _ = is_disqualified_by_culinary_guardrails(
        "concentré", ["concentré", "tomate"], "Sauce bolognaise pur bœuf", "Panzani"
    )
    assert disq_bolo is True

    disq_paste, _ = is_disqualified_by_culinary_guardrails(
        "concentré", ["concentré", "tomate"], "Double concentré de tomates en tube 140g", "SIMPL"
    )
    assert disq_paste is False


# ─────────────────────────────────────────────────────────────────────────────
# 2. Tests du CartMatcherService avec stratégies de budget et multi-magasins
# ─────────────────────────────────────────────────────────────────────────────

def _populate_cache_item(
    session: Session,
    *,
    store: SupermarketStore,
    query: str,
    name: str,
    brand: str,
    price: float,
    packaging: str = "500g",
    sku: str = "sku-test",
) -> SupermarketSearchCache:
    now = datetime.now(UTC)
    row = SupermarketSearchCache(
        store=store,
        query=query,
        external_id=sku,
        name=name,
        brand=brand,
        packaging=packaging,
        price_amount=price,
        price_text=f"{price:.2f} €",
        fetched_at=now,
        expires_at=now + timedelta(days=2),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_cart_matcher_budget_strategy_rejects_expensive_butter(session: Session):
    """When searching for butter on a budget, choose the 2€ store/first-price brand over a 5.50€ luxury butter."""
    store = SupermarketStore.CARREFOUR

    # Seed an overpriced luxury butter and a budget butter
    _populate_cache_item(
        session,
        store=store,
        query="beurre",
        name="Beurre de Baratte AOP d'Isigny Motte Gastronomique",
        brand="Isigny Sainte-Mère",
        price=5.85,
        packaging="250g",
        sku="beurre-luxe-1",
    )
    _populate_cache_item(
        session,
        store=store,
        query="beurre",
        name="Beurre doux pasteurisé SIMPL",
        brand="SIMPL",
        price=1.99,
        packaging="250g",
        sku="beurre-budget-1",
    )
    _populate_cache_item(
        session,
        store=store,
        query="beurre",
        name="Beurre doux CARREFOUR CLASSIC'",
        brand="CARREFOUR CLASSIC'",
        price=2.45,
        packaging="250g",
        sku="beurre-mdd-1",
    )

    item = GroceryItem(user_id=1, name="Beurre", quantity=200, unit="g")
    session.add(item)
    session.commit()
    session.refresh(item)

    # Strategy: "budget"
    matched_budget = CartMatcherService.match_grocery_item(
        session, item, store=store, strategy="budget", user_id=1
    )
    assert matched_budget is not None
    assert matched_budget.external_id == "beurre-budget-1"
    assert matched_budget.unit_price_cents == 199

    # Strategy: "mdd"
    matched_mdd = CartMatcherService.match_grocery_item(
        session, item, store=store, strategy="mdd", user_id=1
    )
    assert matched_mdd is not None
    # MDD or First-price preferred, NEVER the 5.85€ luxury butter
    assert matched_mdd.external_id in ["beurre-budget-1", "beurre-mdd-1"]
    assert matched_mdd.unit_price_cents < 300


def test_cart_matcher_dahl_complete_recipe_no_aberrations(session: Session):
    """Verify that all ingredients for Dahl de lentilles corail map to authentic raw staples with 0% aberrations across stores."""
    store = SupermarketStore.CARREFOUR

    # Seed candidates including traps
    _populate_cache_item(
        session, store=store, query="lentilles corail",
        name="Tranches végétales aux lentilles corail Fleury Michon",
        brand="Fleury Michon", price=4.95, sku="trap-1"
    )
    _populate_cache_item(
        session, store=store, query="lentilles corail",
        name="Lentilles Corail sèches CARREFOUR CLASSIC'",
        brand="CARREFOUR CLASSIC'", price=1.75, sku="lentilles-ok"
    )
    _populate_cache_item(
        session, store=store, query="lait de coco",
        name="Lait de coco fluide brique 200ml",
        brand="CARREFOUR", price=0.89, sku="coco-ok"
    )
    _populate_cache_item(
        session, store=store, query="ail",
        name="Tête d'ail blanc",
        brand="Carrefour", price=0.99, sku="ail-ok"
    )
    _populate_cache_item(
        session, store=store, query="ail",
        name="Bouillon cube ail et persil",
        brand="Knorr", price=1.89, sku="trap-ail"
    )
    _populate_cache_item(
        session, store=store, query="riz",
        name="Riz basmati 1kg",
        brand="CARREFOUR CLASSIC'", price=1.45, sku="riz-ok"
    )

    ingredients = [
        ("Lentilles corail", 150, "g", "lentilles-ok"),
        ("Lait de coco", 20, "cl", "coco-ok"),
        ("Ail", 1, "item", "ail-ok"),
        ("Riz", 120, "g", "riz-ok"),
    ]

    for name, qty, unit, expected_sku in ingredients:
        g_item = GroceryItem(user_id=1, name=name, quantity=qty, unit=unit)
        session.add(g_item)
        session.commit()
        session.refresh(g_item)

        matched = CartMatcherService.match_grocery_item(
            session, g_item, store=store, strategy="budget", user_id=1
        )
        assert matched is not None, f"Échec de matching pour {name}"
        assert matched.external_id == expected_sku, f"Pour '{name}', attendu SKU {expected_sku}, obtenu '{matched.name}' ({matched.external_id})"


def test_first_price_detection_across_all_supported_stores():
    """Verify that hard-discount brands are recognized across all 4 major French chains."""
    assert is_budget_first_price("SIMPL", "Huile de tournesol") is True         # Carrefour
    assert is_budget_first_price("Eco+", "Riz long grain") is True              # E.Leclerc
    assert is_budget_first_price("Pouce", "Farine de blé T55") is True          # Auchan
    assert is_budget_first_price("Top Budget", "Pâtes coquillettes") is True     # Intermarché
    assert is_budget_first_price("Barilla", "Pâtes spaghetti") is False
    assert is_budget_first_price("Fleury Michon", "Jambon blanc") is False


def test_cart_matcher_pasta_salmon_recipe_auchan(session: Session):
    """Verify Auchan shopping for Pâtes au saumon rejects micro-wave trays."""
    store = SupermarketStore.AUCHAN

    # Seed candidates
    _populate_cache_item(
        session, store=store, query="saumon",
        name="Plat cuisiné Pâtes au saumon micro-ondable",
        brand="Fleury Michon", price=4.89, sku="auchan-trap-saumon"
    )
    _populate_cache_item(
        session, store=store, query="saumon",
        name="2 Pavés de saumon frais d'Atlantique 250g",
        brand="Auchan", price=5.49, sku="auchan-saumon-ok"
    )
    _populate_cache_item(
        session, store=store, query="pâtes",
        name="Penne Rigate qualité supérieure 500g",
        brand="Auchan", price=0.95, sku="auchan-penne-ok"
    )
    _populate_cache_item(
        session, store=store, query="crème",
        name="Crème fraîche épaisse entière 30% MG 20cl",
        brand="Auchan", price=0.89, sku="auchan-creme-ok"
    )
    _populate_cache_item(
        session, store=store, query="crème",
        name="Glace crème brûlée vanille 1L",
        brand="La Laitière", price=3.99, sku="auchan-trap-glace"
    )

    saumon_item = GroceryItem(user_id=1, name="Saumon frais", quantity=250, unit="g")
    pates_item = GroceryItem(user_id=1, name="Pâtes penne", quantity=300, unit="g")
    creme_item = GroceryItem(user_id=1, name="Crème fraîche", quantity=20, unit="cl")

    for item, expected_sku in [
        (saumon_item, "auchan-saumon-ok"),
        (pates_item, "auchan-penne-ok"),
        (creme_item, "auchan-creme-ok"),
    ]:
        session.add(item)
        session.commit()
        session.refresh(item)
        matched = CartMatcherService.match_grocery_item(
            session, item, store=store, strategy="mdd", user_id=1
        )
        assert matched is not None
        assert matched.external_id == expected_sku


def test_cart_matcher_intermarche_chicken_budget_rejects_nuggets(session: Session):
    """Verify Intermarché shopping for raw chicken on a budget rejects nuggets."""
    store = SupermarketStore.INTERMARCHE

    _populate_cache_item(
        session, store=store, query="poulet",
        name="Nuggets de poulet panés croustillants x20",
        brand="Top Budget", price=2.99, sku="inter-trap-nugget"
    )
    _populate_cache_item(
        session, store=store, query="poulet",
        name="Filets de poulet jaune x2 250g",
        brand="Volaé, une marque Intermarché", price=3.93, sku="inter-poulet-ok"
    )

    item = GroceryItem(user_id=1, name="Poulet", quantity=300, unit="g")
    session.add(item)
    session.commit()
    session.refresh(item)

    matched = CartMatcherService.match_grocery_item(
        session, item, store=store, strategy="budget", user_id=1
    )
    assert matched is not None
    # Nuggets are disqualified; authentic raw chicken filets match
    assert matched.external_id == "inter-poulet-ok"


def test_cart_matcher_leclerc_ground_beef_rejects_canned_ravioli(session: Session):
    """Verify E.Leclerc shopping for raw beef rejects canned ravioli / pizzas."""
    store = SupermarketStore.LECLERC

    _populate_cache_item(
        session, store=store, query="boeuf",
        name="Ravioli pur bœuf sauce tomate en boîte 800g",
        brand="Eco+", price=1.65, sku="leclerc-trap-ravioli"
    )
    _populate_cache_item(
        session, store=store, query="boeuf",
        name="Viande hachée pur bœuf 15% MG 350g",
        brand="Marque Repère", price=3.99, sku="leclerc-boeuf-ok"
    )

    item = GroceryItem(user_id=1, name="Boeuf haché", quantity=350, unit="g")
    session.add(item)
    session.commit()
    session.refresh(item)

    matched = CartMatcherService.match_grocery_item(
        session, item, store=store, strategy="mdd", user_id=1
    )
    assert matched is not None
    assert matched.external_id == "leclerc-boeuf-ok"


def test_cart_matcher_beans_rejects_chili_prepared_dish(session: Session):
    """Verify raw/canned kidney beans reject microwave chili con carne trays."""
    store = SupermarketStore.CARREFOUR

    _populate_cache_item(
        session, store=store, query="haricots",
        name="Chili con carne traiteur en barquette 400g",
        brand="Marie", price=4.65, sku="carrefour-trap-chili"
    )
    _populate_cache_item(
        session, store=store, query="haricots",
        name="Haricots rouges cuisinés à la mexicaine en boîte",
        brand="Bonduelle", price=2.30, sku="carrefour-trap-mexicain"
    )
    _populate_cache_item(
        session, store=store, query="haricots",
        name="Haricots rouges au naturel SIMPL 400g",
        brand="SIMPL", price=0.79, sku="carrefour-haricots-ok"
    )

    item = GroceryItem(user_id=1, name="Haricots rouges", quantity=400, unit="g")
    session.add(item)
    session.commit()
    session.refresh(item)

    matched = CartMatcherService.match_grocery_item(
        session, item, store=store, strategy="budget", user_id=1
    )
    assert matched is not None
    # Chooses pure staple kidney beans, NOT the prepared microwave chili
    assert matched.external_id == "carrefour-haricots-ok"
    assert matched.unit_price_cents == 79


