from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.models import (
    PantryItem,
    RecipeIngredient,
    SupermarketMapping,
    SupermarketSearchCache,
    SupermarketStore,
)
from app.services.scraper_service import normalize_search_result, upsert_search_cache
from app.services.scrapers.intermarche import (
    extract_category_from_tracking_code,
    extract_category_from_product_breadcrumb,
    infer_category_from_name,
    parse_intermarche_html,
    requires_intermarche_store_selection,
)


def test_parse_intermarche_html_handles_missing_fields():
    html = """
    <div data-testid="product-layout">
      <p class="font-bold font-open-sans">Panzani</p>
      <h2 class="product-title">Pates</h2>
      <div data-testid="default">2,39 €</div>
      <p class="packaging">500 g</p>
      <a class="productcard__link" href="/produits/pates-123"></a>
    </div>
    <div data-testid="product-layout">
      <h2 class="product-title">Lait demi-ecreme</h2>
    </div>
    <div data-testid="product-layout">
      <h2 class="product-title">Beurre</h2>
      <div class="price-box">prix mystere</div>
      <img src="https://img.test/beurre.png" />
    </div>
    """

    results = parse_intermarche_html(html, max_results=10)

    assert len(results) == 3
    assert results[0]["id"] == "pates-123"
    assert results[0]["name"] == "Panzani - Pates"
    assert results[1]["image"] is None
    assert results[1]["product_url"] is None
    assert results[2]["price"] == "prix mystere"


def test_parse_intermarche_html_uses_embedded_category_filters():
    html = r"""
    <div data-testid="product-layout">
      <p class="font-bold font-open-sans">Paquito</p>
      <h2 class="product-title">Jus de pomme</h2>
      <div data-testid="default">1,33 €</div>
      <p class="packaging">les 6 briques de 20cl</p>
      <a class="productcard__link" href="/produit/jus-de-pomme/3250390031062"></a>
    </div>
    <script>
      self.__next_f.push([1,"{\"products\":[{\"url\":\"/produit/jus-de-pomme/3250390031062\",\"famillyId\":15279,\"subFamillyId\":15308,\"departmentId\":15245,\"trackingCode\":\"ODk3YzE3ZWItMGVmZC00YzRjLWJhNjUtZGRmM2YxY2QyZjE4fDg5N2MxN2ViLTBlZmQtNGM0Yy1iYTY1LWRkZjNmMWNkMmYxOHxQYWdlIFLDqXN1bHRhdHN8TGlzdGUgcHJvZHVpdHN8MTQ5NjB8anVzfFBST0RVQ1R8Mzl8U0VBUkNIfG51bGx8UkVTVUxUU19MSVNUfG51bGx8bnVsbHxudWxsfG51bGx8bnVsbHxudWxsfFtTQ0VOQVJJT19QQUdFUkVTVUxUQVRdIEJJTy9NREQvSU5OSVR8MTc3MzU0Mjk0MTAwNXxmci1GUnxDT01QVVRFUg\"}],\"filters\":[{\"type\":\"categories\",\"label\":\"categories\",\"values\":[{\"id\":15279,\"label\":\"Pommes\",\"countProducts\":26}]},{\"type\":\"promotions\",\"label\":\"promotions\",\"values\":[]}]}"])
    </script>
    """

    results = parse_intermarche_html(html, max_results=10)

    assert len(results) == 1
    assert results[0]["category"] == "Pommes"


def test_requires_intermarche_store_selection_detects_modal_copy():
    html = """
    <html>
      <body>
        <div role="dialog">
          <h1>Sélectionner un magasin</h1>
          <button aria-label="storeLocatore.switchBtn.add-list">Liste</button>
        </div>
      </body>
    </html>
    """

    assert requires_intermarche_store_selection(html) is True


def test_extract_category_from_tracking_code_uses_subfamily_label():
    tracking = "ODk3YzE3ZWItMGVmZC00YzRjLWJhNjUtZGRmM2YxY2QyZjE4fDg5N2MxN2ViLTBlZmQtNGM0Yy1iYTY1LWRkZjNmMWNkMmYxOHxQYWdlIFLDqXN1bHRhdHN8TGlzdGUgcHJvZHVpdHN8MTA3N3xwYWluIGRlIG1pZXxQUk9EVUNUfDB8U0VBUkNIfG51bGx8UkVTVUxUU19MSVNUfG51bGx8bnVsbHxudWxsfG51bGx8bnVsbHxudWxsfFtQw6luYWxpc2VyXSBMYSBzb3VzLWZhbWlsbGUgInBhaW4gc2FuZHdpY2ggJiBidXJnZXIiIHBvdXIgbGEgcmVxdcOqdGUgInBhaW4gZGUgbWllInwxNzczNDc3ODIxMzIzfGZyLUZSfENPTVBVVEVS"
    assert extract_category_from_tracking_code(tracking) == "pain sandwich & burger"


def test_extract_category_from_tracking_code_supports_plural_families():
    tracking = "ODk3YzE3ZWItMGVmZC00YzRjLWJhNjUtZGRmM2YxY2QyZjE4fDg5N2MxN2ViLTBlZmQtNGM0Yy1iYTY1LWRkZjNmMWNkMmYxOHxQYWdlIFLDqXN1bHRhdHN8TGlzdGUgcHJvZHVpdHN8MjA5MTIxfHBhaW58UFJPRFVDVHwwfFNFQVJDSHxudWxsfFJFU1VMVFNfTElTVHxudWxsfG51bGx8bnVsbHxudWxsfG51bGx8bnVsbHxbQXZhbnRhZ2VyXSBMZXMgZmFtaWxsZXMgInBhaW4gZnJhaXMiICsgInBhaW4gZGUgbWllIiBkYW5zIGxhIHJlcXXDqnRlICJwYWluInwxNzczNTQyNTQ1NTk1fGZyLUZSfENPTVBVVEVS"
    assert extract_category_from_tracking_code(tracking) == "pain frais / pain de mie"


def test_infer_category_from_name_uses_filter_hints():
    categories = {
        1: "Oranges et Agrumes",
        2: "Multi-fruits",
        3: "Pommes",
    }

    assert infer_category_from_name("/produit/100%25-pur-jus-orange-sans-pulpe/3250391571086", categories) == "Oranges et Agrumes"
    assert infer_category_from_name("/produit/100%25-pur-jus-multifruits/3250390294726", categories) == "Multi-fruits"


def test_extract_category_from_product_breadcrumb_uses_first_button():
    html = """
    <nav aria-label="Fil d’Ariane">
      <a href="/accueil">Accueil</a>
      <ol>
        <li><button>Fromages, Crèmerie et Oeufs</button></li>
        <li><a href="/rayons/laits">Laits et Boissons lactées</a></li>
      </ol>
    </nav>
    """

    assert extract_category_from_product_breadcrumb(html) == "Fromages, Crèmerie et Oeufs"


def test_extract_category_from_product_breadcrumb_uses_json_ld_breadcrumb_list():
    html = """
    <script type="application/ld+json">
      [
        {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          "itemListElement": [
            {"@type": "ListItem", "position": 0, "name": "Fromages, Crèmerie et Oeufs"},
            {"@type": "ListItem", "position": 1, "name": "Laits et Boissons lactées"}
          ]
        }
      ]
    </script>
    """

    assert extract_category_from_product_breadcrumb(html) == "Fromages, Crèmerie et Oeufs"


def test_extract_category_from_product_breadcrumb_falls_back_to_first_link():
    html = """
    <nav aria-label="Fil d’Ariane">
      <ol>
        <li><a href="/rayons/boissons">Boissons</a></li>
        <li><a href="/rayons/jus">Jus de fruits</a></li>
      </ol>
    </nav>
    """

    assert extract_category_from_product_breadcrumb(html) == "Boissons"


def test_normalize_search_result_parses_price_and_keeps_missing_fields():
    normalized = normalize_search_result(
        SupermarketStore.INTERMARCHE,
        "lait",
        {
            "id": "sku-1",
            "name": "Lait",
            "price": "1,49 € /l",
            "image": None,
        },
    )

    assert normalized["price_amount"] == 1.49
    assert normalized["price_text"] == "1,49 € /l"
    assert normalized["packaging"] is None
    assert normalized["product_url"] is None


def test_upsert_search_cache_deduplicates_recent_entries(test_engine):
    with Session(test_engine) as session:
        first = upsert_search_cache(
            session,
            SupermarketStore.INTERMARCHE,
            [
                {
                    "store": SupermarketStore.INTERMARCHE,
                    "query": "lait",
                    "external_id": "sku-1",
                    "name": "Lait entier",
                    "brand": "Candia",
                    "packaging": "1 L",
                    "price_amount": 1.59,
                    "price_text": "1,59 €",
                    "image_url": None,
                    "product_url": "https://example.test/lait",
                    "payload_json": {"raw": 1},
                }
            ],
        )
        second = upsert_search_cache(
            session,
            SupermarketStore.INTERMARCHE,
            [
                {
                    "store": SupermarketStore.INTERMARCHE,
                    "query": "lait",
                    "external_id": "sku-1",
                    "name": "Lait entier",
                    "brand": "Candia",
                    "packaging": "1 L",
                    "price_amount": 1.69,
                    "price_text": "1,69 €",
                    "image_url": None,
                    "product_url": "https://example.test/lait",
                    "payload_json": {"raw": 2},
                }
            ],
        )

        assert len(first) == 1
        assert len(second) == 1
        assert first[0].id == second[0].id

        rows = session.exec(select(SupermarketSearchCache)).all()
        assert len(rows) == 1
        assert rows[0].price_text == "1,69 €"


def test_supermarket_search_and_mapping_endpoints(client, auth_headers, monkeypatch):
    async def fake_fetch_search_results(store, queries, max_results=10, promotions_only=False):
        assert store == SupermarketStore.INTERMARCHE
        assert queries == ["lait"]
        return [
            {
                "store": SupermarketStore.INTERMARCHE,
                "query": "lait",
                "external_id": "sku-lait",
                "name": "Candia - Lait demi-ecreme",
                "brand": "Candia",
                "packaging": "1 L",
                "price_amount": 1.49,
                "price_text": "1,49 €",
                "image_url": "https://img.test/lait.png",
                "product_url": "https://example.test/lait",
                "payload_json": {"raw": True},
            }
        ]

    monkeypatch.setattr("app.api.endpoints.supermarket.fetch_search_results", fake_fetch_search_results)

    recipe = client.post(
        "/api/v1/recipes",
        headers=auth_headers,
        json={
            "name": "Gateau",
            "instructions": "Melanger",
            "ingredients": [{"name": "Lait", "quantity": 1, "unit": "L"}],
        },
    )
    assert recipe.status_code == 200
    ingredient_id = recipe.json()["ingredients"][0]["id"]

    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Lait", "quantity": 2, "unit": "L", "min_quantity": 0},
    )
    assert pantry.status_code == 200
    pantry_id = pantry.json()["id"]

    search = client.post(
        "/api/v1/supermarket/search",
        headers=auth_headers,
        json={"store": "intermarche", "queries": ["lait"], "max_results": 5},
    )
    assert search.status_code == 200
    results = search.json()
    assert len(results) == 1
    cache_id = results[0]["cache_id"]

    recipe_mapping = client.put(
        f"/api/v1/supermarket/mappings/recipe-ingredients/{ingredient_id}",
        headers=auth_headers,
        json={
            "cache_id": cache_id,
            "store": "intermarche",
            "external_id": "sku-lait",
            "store_label": "Intermarché",
            "name_snapshot": "Candia - Lait demi-ecreme",
            "packaging_snapshot": "1 L",
            "price_snapshot": "1,49 €",
            "product_url": "https://example.test/lait",
            "image_url": "https://img.test/lait.png",
        },
    )
    assert recipe_mapping.status_code == 200
    recipe_mapping_id = recipe_mapping.json()["id"]

    pantry_mapping = client.put(
        f"/api/v1/supermarket/mappings/pantry-items/{pantry_id}",
        headers=auth_headers,
        json={
            "store": "intermarche",
            "external_id": "sku-lait",
            "store_label": "Intermarché",
            "name_snapshot": "Candia - Lait demi-ecreme",
            "packaging_snapshot": "1 L",
            "price_snapshot": "1,49 €",
            "product_url": "https://example.test/lait",
            "image_url": "https://img.test/lait.png",
        },
    )
    assert pantry_mapping.status_code == 200

    read_recipe_mapping = client.get(
        f"/api/v1/supermarket/mappings/recipe-ingredients/{ingredient_id}",
        headers=auth_headers,
    )
    assert read_recipe_mapping.status_code == 200
    assert read_recipe_mapping.json()["external_id"] == "sku-lait"

    replaced = client.put(
        f"/api/v1/supermarket/mappings/recipe-ingredients/{ingredient_id}",
        headers=auth_headers,
        json={
            "store": "intermarche",
            "external_id": "sku-lait-2",
            "store_label": "Intermarché",
            "name_snapshot": "Candia - Lait bio",
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["external_id"] == "sku-lait-2"

    deleted = client.delete(f"/api/v1/supermarket/mappings/{recipe_mapping_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert deleted.json()["active"] is False


def test_mapping_rejects_invalid_target_and_store(client, auth_headers):
    invalid_target = client.put(
        "/api/v1/supermarket/mappings/pantry-items/9999",
        headers=auth_headers,
        json={
            "store": "intermarche",
            "external_id": "sku-x",
            "store_label": "Intermarché",
            "name_snapshot": "Produit",
        },
    )
    assert invalid_target.status_code == 404

    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Farine", "quantity": 1, "unit": "kg", "min_quantity": 0},
    )
    pantry_id = pantry.json()["id"]
    invalid_store = client.put(
        f"/api/v1/supermarket/mappings/pantry-items/{pantry_id}",
        headers=auth_headers,
        json={
            "store": "leclerc",
            "external_id": "sku-x",
            "store_label": "Leclerc",
            "name_snapshot": "Farine",
        },
    )
    assert invalid_store.status_code == 422
