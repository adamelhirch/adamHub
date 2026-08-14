from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app.models import (
    PantryItem,
    RecipeIngredient,
    SupermarketMapping,
    SupermarketSearchCache,
    SupermarketStore,
)
from app.services.connections import (
    decrypt_cookies,
    decrypt_credentials,
    upsert_connection,
)
from app.services.store_catalog import list_store_definitions, normalize_search_result, upsert_search_cache
from app.services.scrapers.auchan import parse_auchan_search_html, search_auchan
from app.services.scrapers.intermarche import (
    extract_category_from_tracking_code,
    extract_category_from_product_breadcrumb,
    infer_category_from_name,
    parse_intermarche_html,
    requires_intermarche_store_selection,
)
from app.services.scrapers.leclerc import parse_leclerc_search_html, search_leclerc


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
    async def fake_fetch_search_results(store, queries, max_results=10, promotions_only=False, sort_by=None, session=None, user_id=None):
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
    assert pantry_mapping.status_code == 200

    read_recipe_mapping = client.get(
        f"/api/v1/supermarket/mappings/recipe-ingredients/{ingredient_id}",
        headers=auth_headers,
    )
    assert read_recipe_mapping.status_code == 200
    assert read_recipe_mapping.json()["external_id"] == "sku-lait"

    # Snapshot fields are resolved from the cache row, so the fabricated
    # external_id below is ignored in favor of the cache's value.
    replaced = client.put(
        f"/api/v1/supermarket/mappings/recipe-ingredients/{ingredient_id}",
        headers=auth_headers,
        json={
            "cache_id": cache_id,
            "store": "intermarche",
            "external_id": "sku-lait-2",
            "store_label": "Intermarché",
            "name_snapshot": "Candia - Lait bio",
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["external_id"] == "sku-lait"
    assert replaced.json()["name_snapshot"] == "Candia - Lait demi-ecreme"

    deleted = client.delete(f"/api/v1/supermarket/mappings/{recipe_mapping_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert deleted.json()["active"] is False


def _seed_search_cache(test_engine, external_id="sku-x", name="Produit"):
    now = datetime.now(UTC)
    with Session(test_engine) as session:
        row = SupermarketSearchCache(
            store=SupermarketStore.INTERMARCHE,
            query="produit",
            external_id=external_id,
            name=name,
            packaging="1 pièce",
            price_amount=1.0,
            price_text="1,00 €",
            fetched_at=now,
            expires_at=now + timedelta(days=1),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def test_mapping_rejects_invalid_target_and_store(client, auth_headers, test_engine):
    cache_id = _seed_search_cache(test_engine)

    invalid_target = client.put(
        "/api/v1/supermarket/mappings/pantry-items/9999",
        headers=auth_headers,
        json={
            "cache_id": cache_id,
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
            "cache_id": cache_id,
            "store": "monoprix",
            "external_id": "sku-x",
            "store_label": "Monoprix",
            "name_snapshot": "Farine",
        },
    )
    assert invalid_store.status_code == 422


def test_mapping_rejects_fabricated_snapshot_without_cache_id(client, auth_headers):
    pantry = client.post(
        "/api/v1/pantry/items",
        headers=auth_headers,
        json={"name": "Farine", "quantity": 1, "unit": "kg", "min_quantity": 0},
    )
    assert pantry.status_code == 200
    pantry_id = pantry.json()["id"]

    no_cache = client.put(
        f"/api/v1/supermarket/mappings/pantry-items/{pantry_id}",
        headers=auth_headers,
        json={
            "store": "intermarche",
            "external_id": "sku-fake",
            "store_label": "Intermarché",
            "name_snapshot": "Farine",
        },
    )
    assert no_cache.status_code == 422


# ── P3: Leclerc + Auchan (Drive) registry, parsers and credentials ────────────


def test_store_registry_lists_five_stores_including_leclerc_and_auchan():
    definitions = list_store_definitions()
    keys = [definition.key for definition in definitions]
    assert len(keys) == 5
    assert SupermarketStore.INTERMARCHE in keys
    assert SupermarketStore.UBEREATS in keys
    assert SupermarketStore.CARREFOUR in keys
    assert SupermarketStore.LECLERC in keys
    assert SupermarketStore.AUCHAN in keys

    leclerc = next(d for d in definitions if d.key == SupermarketStore.LECLERC)
    auchan = next(d for d in definitions if d.key == SupermarketStore.AUCHAN)
    assert leclerc.label == "Leclerc"
    assert auchan.label == "Auchan"
    assert leclerc.supports_search is True
    assert auchan.supports_search is True
    assert leclerc.scraper_name == "leclerc"
    assert auchan.scraper_name == "auchan"


def test_leclerc_parser_extracts_embedded_json_from_search_html():
    html = """
    <script>
      Utilitaires.widget.initOptions('ctl00_ctl00_mainMutiUnivers_main_ctl04_pnlElementProduit',
        {"objContenu":{"lstElements":[
          {"objElement":{"iIdProduit":32452,"sId":"32452",
            "sLibelleLigne1":"Lait de montagne D&#233;lisse",
            "sLibelleLigne2":"UHT Bouteille - 6x1L",
            "sPrixUnitaire":"6,72 €","nrPVUnitaireTTC":6.72,
            "sPrixParUniteDeMesure":"1,12 € / l",
            "sUrlVignetteProduit":"https://fd7-photos.leclercdrive.fr/image.ashx?id=2929937",
            "sUrlPageProduit":"https://fd7-courses.leclercdrive.fr/magasin-123111-123111-Montaudran/fiche-produits-32452-Lait-de-montagne-Delisse.aspx",
            "sCategorie":30}},
          {"objElement":{"iIdProduit":2612,
            "sLibelleLigne1":"Lait demi-&#233;cr&#233;m&#233; UHT D&#233;lisse",
            "sLibelleLigne2":"Brique - 6x1L","sPrixUnitaire":"5,94 €",
            "sUrlVignetteProduit":"https://fd7-photos.leclercdrive.fr/image.ashx?id=2970545",
            "sCategorie":40}}
        ]}});
    </script>
    """
    items = parse_leclerc_search_html(html, max_results=10)
    assert len(items) == 2
    normalized = [
        normalize_search_result(SupermarketStore.LECLERC, "lait", item) for item in items
    ]
    assert normalized[0]["name"] == "Lait de montagne Délisse"
    assert normalized[0]["external_id"] == "32452"
    assert normalized[0]["price_text"] == "6,72 €"
    assert normalized[0]["price_amount"] == 6.72
    assert normalized[0]["product_url"].endswith("fiche-produits-32452-Lait-de-montagne-Delisse.aspx")
    assert normalized[0]["image_url"] == "https://fd7-photos.leclercdrive.fr/image.ashx?id=2929937"
    assert normalized[1]["name"] == "Lait demi-écrémé UHT Délisse"


def test_auchan_parser_extracts_product_cards_from_search_html():
    html = """
    <article itemscope itemtype="http://schema.org/Product"
             class="product-thumbnail list__item" data-id="130ef860-aa6d-46f1-abb4-76ea4fce5214">
      <a class="product-thumbnail__details-wrapper"
         href="/lait-de-savoie-lait-demi-ecreme-uht/pr-C1799228"
         data-id="130ef860-aa6d-46f1-abb4-76ea4fce5214">
        <p class="product-thumbnail__description" itemprop="name description">
          <strong itemprop="brand">LAIT DE SAVOIE</strong>
          Lait demi-écrémé UHT 6x1l
        </p>
        <div class="product-thumbnail__attributes">
          <span class="product-attribute" aria-label="Contenance : 6x1l">6x1l</span>
        </div>
        <meta itemprop="image" content="https://cdn.auchan.fr/media/S01000000040V28PRIMARY_0x0/B2CD/">
      </a>
    </article>
    """
    items = parse_auchan_search_html(html, max_results=10)
    assert len(items) == 1
    normalized = [
        normalize_search_result(SupermarketStore.AUCHAN, "lait", item) for item in items
    ]
    assert normalized[0]["name"] == "Lait demi-écrémé UHT 6x1l"
    assert normalized[0]["external_id"] == "130ef860-aa6d-46f1-abb4-76ea4fce5214"
    assert normalized[0]["product_url"] == "https://www.auchan.fr/lait-de-savoie-lait-demi-ecreme-uht/pr-C1799228"
    assert normalized[0]["image_url"] == "https://cdn.auchan.fr/media/S01000000040V28PRIMARY_0x0/B2CD/"
    assert normalized[0]["price_text"] is None  # price is lazy-loaded, not in HTML


def test_leclerc_and_auchan_search_raise_without_cookies_offline():
    import asyncio

    with pytest.raises(RuntimeError):
        asyncio.run(search_leclerc(queries=["lait"], cookies=[]))
    with pytest.raises(RuntimeError):
        asyncio.run(search_auchan(queries=["lait"], cookies=[]))


def test_connection_import_with_credentials_stores_encrypted(test_engine):
    with Session(test_engine) as session:
        connection = upsert_connection(
            session,
            store=SupermarketStore.LECLERC,
            label="leclerc-creds",
            cookies=[],
            credentials={"username": "user@example.com", "password": "s3cret"},
            activate=True,
        )
        assert connection.cookies_encrypted != '{"username": "user@example.com", "password": "s3cret"}'
        assert decrypt_credentials(connection) == {
            "username": "user@example.com",
            "password": "s3cret",
        }
        assert decrypt_cookies(connection) == []
