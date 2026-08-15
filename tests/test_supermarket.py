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
    build_search_query,
    extract_category_from_tracking_code,
    extract_pdv_ref_from_cookies,
    parse_intermarche_category_tree,
    parse_intermarche_products,
)
from app.services.scrapers.leclerc import parse_leclerc_search_html, search_leclerc


def _load_intermarche_fixture():
    import json
    from pathlib import Path

    fixture_path = Path(__file__).resolve().parent / "fixtures" / "intermarche_products.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_parse_intermarche_products_handles_missing_fields():
    payload = {"products": [
        {
            "id": "sku-1",
            "ean": None,
            "url": "/produit/pates-123",
            "informations": {
                "title": "Panzani - Pates",
                "brand": "Panzani",
                "packaging": "500 g",
                "image": {"src": None},
            },
            "prices": {"productPrice": {"concatenated": "2,39€"}},
            "trackingCode": None,
        },
        {
            "id": "sku-2",
            "informations": {"title": "Lait demi-ecreme"},
            "prices": {},
        },
        {
            "id": "sku-3",
            "informations": {"title": "Beurre"},
            "prices": {"productPrice": {"value": 1.2, "currency": "€"}},
        },
    ], "meta": {}}

    results = parse_intermarche_products(payload, max_results=10)

    assert len(results) == 3
    assert results[0]["id"] == "sku-1"
    assert results[0]["name"] == "Panzani - Pates"
    assert results[0]["product_url"] == "https://www.intermarche.com/produit/pates-123"
    assert results[1]["image"] is None
    assert results[1]["product_url"] is None
    assert results[1]["price"] is None
    assert results[2]["price"] == "1,2€"


def test_parse_intermarche_products_skips_editorial_tiles_without_product_id():
    payload = {"products": [
        {
            "type": "PDV",
            "url": "/produit/product/undefined",
            "partnerTile": {"id": "21123", "kind": "RECIPE", "datas": {"title": "Flan express"}},
            "informations": {"title": None, "brand": None},
            "prices": None,
        },
        {
            "id": "sku-1",
            "ean": "3250390011866",
            "url": "/produit/lait/3250390011866",
            "informations": {"title": "Lait", "brand": "Candia", "packaging": "1 L"},
            "prices": {"productPrice": {"concatenated": "1,49€"}},
        },
    ], "meta": {}}

    results = parse_intermarche_products(payload, max_results=10)

    assert len(results) == 1
    assert results[0]["id"] == "3250390011866"


def test_parse_intermarche_products_uses_category_lookup_preferring_deepest_family():
    payload = {"products": [
        {
            "id": "sku-1",
            "ean": "3176571626004",
            "url": "/produit/lait/3176571626004",
            "famillyId": 5961,
            "subFamillyId": 0,
            "departmentId": 2233,
            "informations": {"title": "Lait", "brand": "Grandlait"},
            "prices": {"productPrice": {"concatenated": "4,08€"}},
            "trackingCode": None,
        }
    ], "meta": {}}
    category_lookup = {
        2233: "Fromages, Crèmerie et Oeufs / Laits et Boissons lactées",
        5961: "Fromages, Crèmerie et Oeufs / Laits et Boissons lactées / Laits demi-écrémés",
    }

    results = parse_intermarche_products(payload, max_results=10, category_lookup=category_lookup)

    assert results[0]["category"] == (
        "Fromages, Crèmerie et Oeufs / Laits et Boissons lactées / Laits demi-écrémés"
    )


def test_parse_intermarche_products_falls_back_to_tracking_code_without_lookup():
    payload = {"products": [
        {
            "id": "sku-1",
            "ean": "3250390011866",
            "url": "/produit/pain/3250390011866",
            "famillyId": 5961,
            "informations": {"title": "Pain", "brand": "Boulange"},
            "prices": {"productPrice": {"concatenated": "1,00€"}},
            "trackingCode": "ODk3YzE3ZWItMGVmZC00YzRjLWJhNjUtZGRmM2YxY2QyZjE4fDg5N2MxN2ViLTBlZmQtNGM0Yy1iYTY1LWRkZjNmMWNkMmYxOHxQYWdlIFLDqXN1bHRhdHN8TGlzdGUgcHJvZHVpdHN8MTA3N3xwYWluIGRlIG1pZXxQUk9EVUNUfDB8U0VBUkNIfG51bGx8UkVTVUxUU19MSVNUfG51bGx8bnVsbHxudWxsfG51bGx8bnVsbHxudWxsfFtQw6luYWxpc2VyXSBMYSBzb3VzLWZhbWlsbGUgInBhaW4gc2FuZHdpY2ggJiBidXJnZXIiIHBvdXIgbGEgcmVxdcOqdGUgInBhaW4gZGUgbWllInwxNzczNDc3ODIxMzIzfGZyLUZSfENPTVBVVEVS",
        }
    ], "meta": {}}

    results = parse_intermarche_products(payload, max_results=10)

    assert results[0]["category"] == "pain sandwich & burger"


def test_parse_intermarche_products_maps_real_fixture_products():
    payload = _load_intermarche_fixture()

    results = parse_intermarche_products(payload, max_results=10)

    assert len(results) == 8
    normalized = normalize_search_result(SupermarketStore.INTERMARCHE, "lait", results[0])
    assert normalized["external_id"] == "3176571626004"
    assert normalized["name"] == "Grandlait - Lait demi écrémé"
    assert normalized["brand"] == "Grandlait"
    assert normalized["packaging"] == "les 4 bouteilles de 50cl - 200cl"
    assert normalized["price_text"] == "4,08€"
    assert normalized["price_amount"] == 4.08
    assert normalized["product_url"].startswith("https://www.intermarche.com/produit/")
    assert normalized["image_url"].startswith("https://")


def test_build_search_query_encodes_sort_and_promotions_only():
    default = build_search_query("lait")
    assert default["sort"] == {"type": "pertinence", "direction": None}
    assert default["isPromo"] is False

    asc = build_search_query("lait", sort_by="price_asc")
    assert asc["sort"] == {"type": "prix", "direction": "croissant"}

    desc = build_search_query("lait", sort_by="price_desc")
    assert desc["sort"] == {"type": "prix", "direction": "decroissant"}

    promo = build_search_query("lait", promotions_only=True)
    assert promo["isPromo"] is True


def test_extract_pdv_ref_from_cookies_reads_itm_pdv_cookie():
    cookies = [
        {"name": "itm_pdv", "value": "{%22ref%22:%2211131%22%2C%22name%22:%22Super%22}"},
        {"name": "novaParams", "value": "{%22pdvRef%22:%229999%22}"},
    ]
    assert extract_pdv_ref_from_cookies(cookies) == "11131"

    assert extract_pdv_ref_from_cookies([{"name": "other", "value": "x"}]) is None
    assert extract_pdv_ref_from_cookies([{"name": "itm_pdv", "value": "not-json"}]) is None


def test_parse_intermarche_category_tree_flattens_paths():
    tree = [
        {
            "id": "2233",
            "title": "Fromages, Crèmerie et Oeufs",
            "children": [
                {"id": "5961", "title": "Laits demi-écrémés", "children": []}
            ],
        }
    ]

    lookup = parse_intermarche_category_tree(tree)

    assert lookup[2233] == "Fromages, Crèmerie et Oeufs"
    assert lookup[5961] == "Fromages, Crèmerie et Oeufs / Laits demi-écrémés"


def test_extract_category_from_tracking_code_uses_subfamily_label():
    tracking = "ODk3YzE3ZWItMGVmZC00YzRjLWJhNjUtZGRmM2YxY2QyZjE4fDg5N2MxN2ViLTBlZmQtNGM0Yy1iYTY1LWRkZjNmMWNkMmYxOHxQYWdlIFLDqXN1bHRhdHN8TGlzdGUgcHJvZHVpdHN8MTA3N3xwYWluIGRlIG1pZXxQUk9EVUNUfDB8U0VBUkNIfG51bGx8UkVTVUxUU19MSVNUfG51bGx8bnVsbHxudWxsfG51bGx8bnVsbHxudWxsfFtQw6luYWxpc2VyXSBMYSBzb3VzLWZhbWlsbGUgInBhaW4gc2FuZHdpY2ggJiBidXJnZXIiIHBvdXIgbGEgcmVxdcOqdGUgInBhaW4gZGUgbWllInwxNzczNDc3ODIxMzIzfGZyLUZSfENPTVBVVEVS"
    assert extract_category_from_tracking_code(tracking) == "pain sandwich & burger"


def test_extract_category_from_tracking_code_supports_plural_families():
    tracking = "ODk3YzE3ZWItMGVmZC00YzRjLWJhNjUtZGRmM2YxY2QyZjE4fDg5N2MxN2ViLTBlZmQtNGM0Yy1iYTY1LWRkZjNmMWNkMmYxOHxQYWdlIFLDqXN1bHRhdHN8TGlzdGUgcHJvZHVpdHN8MjA5MTIxfHBhaW58UFJPRFVDVHwwfFNFQVJDSHxudWxsfFJFU1VMVFNfTElTVHxudWxsfG51bGx8bnVsbHxudWxsfG51bGx8bnVsbHxbQXZhbnRhZ2VyXSBMZXMgZmFtaWxsZXMgInBhaW4gZnJhaXMiICsgInBhaW4gZGUgbWllIiBkYW5zIGxhIHJlcXXDqnRlICJwYWluInwxNzczNTQyNTQ1NTk1fGZyLUZSfENPTVBVVEVS"
    assert extract_category_from_tracking_code(tracking) == "pain frais / pain de mie"


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
             class="product-thumbnail list__item"
             data-id="6baf949f-7d78-4d36-8458-3e96f5637688"
             data-current-offer-id="789f635b-a479-5fbb-bd89-002578598430">
      <a class="product-thumbnail__details-wrapper"
         href="/c-est-qui-le-patron-lait-demi-ecreme-equitable-uht/pr-C1169523"
         data-id="6baf949f-7d78-4d36-8458-3e96f5637688">
        <meta itemprop="image" content="https://cdn.auchan.fr/media/P020000000002QOPRIMARY_0x0/B2CD/">
        <div class="product-thumbnail__details">
          <p class="product-thumbnail__description" itemprop="name description">
            <strong itemprop="brand">C'EST QUI LE PATRON ?!</strong>
            Lait demi-écrémé équitable UHT
          </p>
          <div class="product-thumbnail__attributes">
            <span class="product-attribute" aria-label="Contenance : 6x1L">6x1L</span>
          </div>
        </div>
      </a>
      <footer class="product-thumbnail__footer">
        <div class="product-thumbnail__price product-price__container"
             itemprop="offers" itemscope itemtype="http://schema.org/Offer">
          <div class="product-price bolder text-dark-color">7,62€</div>
          <meta itemprop="price" content="7.62">
          <meta itemprop="priceCurrency" content="EUR">
        </div>
        <div class="quantity-selector quantity-selector--default"
             data-product-id="6baf949f-7d78-4d36-8458-3e96f5637688"
             data-offer-id="789f635b-a479-5fbb-bd89-002578598430"
             data-seller-id="4c663296-54a8-45f6-b385-0be86b4dfe98">
        </div>
      </footer>
    </article>
    """
    items = parse_auchan_search_html(html, max_results=10)
    assert len(items) == 1
    normalized = [
        normalize_search_result(SupermarketStore.AUCHAN, "lait", item) for item in items
    ]
    assert normalized[0]["name"] == "Lait demi-écrémé équitable UHT"
    assert normalized[0]["external_id"] == "6baf949f-7d78-4d36-8458-3e96f5637688"
    assert normalized[0]["product_url"] == "https://www.auchan.fr/c-est-qui-le-patron-lait-demi-ecreme-equitable-uht/pr-C1169523"
    assert normalized[0]["price_text"] == "7,62 €"
    assert normalized[0]["price_amount"] == 7.62
    # cart identifiers are preserved in the raw item
    assert items[0]["offer_id"] == "789f635b-a479-5fbb-bd89-002578598430"
    assert items[0]["seller_id"] == "4c663296-54a8-45f6-b385-0be86b4dfe98"


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
