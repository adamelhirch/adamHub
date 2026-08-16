from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
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
from app.services.store_catalog import (
    fetch_search_results,
    get_selected_store,
    list_store_definitions,
    normalize_search_result,
    upsert_search_cache,
    upsert_selected_store,
)
from app.services.scrapers.auchan import (
    AuchanStoreContext,
    AuchanStoreSelectionError,
    parse_auchan_offering_contexts,
    parse_auchan_search_html,
    search_auchan,
)
from app.services.scrapers.intermarche import (
    build_search_query,
    extract_category_from_tracking_code,
    extract_pdv_ref_from_cookies,
    parse_intermarche_category_tree,
    parse_intermarche_products,
)
from app.services.scrapers.leclerc import (
    LECLERC_SORT_IDS,
    LeclercAuthError,
    parse_leclerc_search_html,
    search_leclerc,
)

LECLERC_FIXTURE = Path(__file__).parent / "fixtures" / "leclerc" / "recherche_lait.html"


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
    assert results[0]["store"] == "Intermarché"
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
    assert results[0]["store"] == "Intermarché"
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


def test_store_registry_lists_four_stores_including_leclerc_and_auchan():
    definitions = list_store_definitions()
    keys = [definition.key for definition in definitions]
    assert len(keys) == 4
    assert SupermarketStore.INTERMARCHE in keys
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
    # Leclerc has no promotions-only query flag; the capability is only exposed
    # on stores that implement it (Intermarché + Carrefour).
    assert leclerc.supports_promotions is False
    assert auchan.supports_promotions is False
    intermarche = next(d for d in definitions if d.key == SupermarketStore.INTERMARCHE)
    assert intermarche.supports_promotions is True
    carrefour = next(d for d in definitions if d.key == SupermarketStore.CARREFOUR)
    assert carrefour.supports_promotions is True

    # Every store supports sorting (param/JSON field confirmed live by T2-T5).
    assert all(d.supports_sort for d in definitions)
    # None of the four requires a logged-in account for search-with-price, but
    # all require a store context for store-specific prices.
    assert all(d.requires_login is False for d in definitions)
    assert all(d.requires_store_selection for d in definitions)


def test_supermarket_stores_endpoint_exposes_capability_flags(client, auth_headers):
    response = client.get("/api/v1/supermarket/stores", headers=auth_headers)
    assert response.status_code == 200
    stores = {entry["key"]: entry for entry in response.json()}
    assert set(stores) == {"intermarche", "carrefour", "leclerc", "auchan"}

    intermarche = stores["intermarche"]
    assert intermarche["supports_sort"] is True
    assert intermarche["supports_promotions"] is True
    assert intermarche["requires_store_selection"] is True
    assert intermarche["requires_login"] is False

    carrefour = stores["carrefour"]
    assert carrefour["supports_sort"] is True
    assert carrefour["supports_promotions"] is True

    leclerc = stores["leclerc"]
    assert leclerc["supports_sort"] is True
    assert leclerc["supports_promotions"] is False
    assert leclerc["requires_login"] is False

    auchan = stores["auchan"]
    assert auchan["supports_sort"] is True
    assert auchan["supports_promotions"] is False
    assert auchan["requires_store_selection"] is True
    assert auchan["requires_login"] is False


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
    assert items[0]["store"] == "Leclerc"
    assert items[1]["store"] == "Leclerc"
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


def test_leclerc_parser_against_real_fixture_offline():
    """Parse the reduced fixture derived from the live 936 KB fd7 HAR body.

    The fixture keeps five real `objElement` entries (names, prices, category,
    images, product URLs) plus the real sort widget datasource, so the parser is
    exercised on authentic markup without any network access.
    """
    html = LECLERC_FIXTURE.read_text(encoding="utf-8")
    items = parse_leclerc_search_html(html, max_results=10)

    assert len(items) == 5
    assert items[0]["id"] == "32452"
    assert items[0]["name"] == "Lait de montagne Délisse"
    assert items[0]["packaging"] == "UHT Bouteille - 6x1L"
    assert items[0]["price"] == "6,72 €"
    assert items[0]["price_per_unit"] == "1,12 € / l"
    assert items[0]["category"] == "30"
    assert items[0]["image"].startswith("https://fd7-photos.leclercdrive.fr/image.ashx?id=2929937")
    assert items[0]["product_url"].endswith("fiche-produits-32452-Lait-de-montagne-Delisse.aspx")
    assert items[0]["store"] == "Leclerc"
    assert items[3]["packaging"] == "UHT Bouteille - 6x50cl"
    assert items[4]["category"] == "30"


def test_leclerc_parser_respects_max_results_on_real_fixture():
    html = LECLERC_FIXTURE.read_text(encoding="utf-8")
    assert len(parse_leclerc_search_html(html, max_results=2)) == 2


def test_leclerc_sort_ids_match_site_tri_datasource():
    assert LECLERC_SORT_IDS == {
        "default": 1,
        "price_asc": 2,
        "price_desc": 3,
        "price_per_unit_asc": 4,
        "price_per_unit_desc": 5,
        "best_rated": 6,
    }


class _FakeLeclercClient:
    """Records requests issued by `search_leclerc`; no network involved."""

    def __init__(self, requests: list, **kwargs):
        self._requests = requests
        self._kwargs = kwargs

    async def __aenter__(self) -> "_FakeLeclercClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def get(self, url, params=None, headers=None):
        self._requests.append((str(url), dict(params or {})))
        return httpx.Response(200, text="<html></html>", request=httpx.Request("GET", str(url)))


def _run_search_leclerc_with_fake_client(cookies, **kwargs):
    import asyncio
    from unittest import mock

    requests: list = []

    def fake_client_cls(**client_kwargs):
        return _FakeLeclercClient(requests, **client_kwargs)

    with mock.patch(
        "app.services.scrapers.leclerc.httpx.AsyncClient", side_effect=fake_client_cls
    ):
        asyncio.run(
            search_leclerc(
                queries=["lait"],
                cookies=cookies,
                store_base_url="https://fd7-courses.leclercdrive.fr/magasin-123111-123111-Montaudran",
                **kwargs,
            )
        )
    return requests


def test_leclerc_search_sends_tri_param_for_sort_by():
    cookies = [{"name": "x", "value": "y", "domain": ".leclercdrive.fr"}]
    requests = _run_search_leclerc_with_fake_client(cookies, sort_by="price_asc")

    assert len(requests) == 1
    url, params = requests[0]
    assert url == "https://fd7-courses.leclercdrive.fr/magasin-123111-123111-Montaudran/recherche.aspx"
    assert params == {"TexteRecherche": "lait", "tri": 2}


def test_leclerc_search_omits_tri_param_by_default():
    cookies = [{"name": "x", "value": "y", "domain": ".leclercdrive.fr"}]
    requests = _run_search_leclerc_with_fake_client(cookies)

    _, params = requests[0]
    assert params == {"TexteRecherche": "lait"}


def test_leclerc_search_accepts_promotions_only_without_query_flag():
    cookies = [{"name": "x", "value": "y", "domain": ".leclercdrive.fr"}]
    requests = _run_search_leclerc_with_fake_client(cookies, promotions_only=True)

    _, params = requests[0]
    assert params == {"TexteRecherche": "lait"}


class _FakeStatusLeclercClient:
    def __init__(self, status: int, text: str, **kwargs):
        self._response = httpx.Response(
            status, text=text, request=httpx.Request("GET", "https://x.test/")
        )

    async def __aenter__(self) -> "_FakeStatusLeclercClient":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def get(self, url, params=None, headers=None):
        return self._response


def test_leclerc_search_raises_datadome_challenge_on_403_probe():
    import asyncio
    from unittest import mock

    probe_body = (
        '<html lang="fr"><head><title>leclercdrive.fr</title></head><body>'
        'Please enable JS and disable any ad blocker'
        "<script data-cfasync=\"false\">var dd={'rt':'i','cid':'abc','hsh':'def'};</script>"
        "</body></html>"
    )

    def fake_client_cls(**kwargs):
        return _FakeStatusLeclercClient(403, probe_body)

    with mock.patch(
        "app.services.scrapers.leclerc.httpx.AsyncClient", side_effect=fake_client_cls
    ):
        with pytest.raises(LeclercAuthError, match="anti-bot challenge"):
            asyncio.run(
                search_leclerc(
                    queries=["lait"],
                    cookies=[{"name": "x", "value": "y", "domain": ".leclercdrive.fr"}],
                    store_base_url="https://fd7-courses.leclercdrive.fr/magasin-123111-123111-Montaudran",
                )
            )


def test_leclerc_search_raises_generic_session_error_on_plain_403():
    import asyncio
    from unittest import mock

    def fake_client_cls(**kwargs):
        return _FakeStatusLeclercClient(403, "<html>Forbidden</html>")

    with mock.patch(
        "app.services.scrapers.leclerc.httpx.AsyncClient", side_effect=fake_client_cls
    ):
        with pytest.raises(LeclercAuthError, match="rejected the current session"):
            asyncio.run(
                search_leclerc(
                    queries=["lait"],
                    cookies=[{"name": "x", "value": "y", "domain": ".leclercdrive.fr"}],
                    store_base_url="https://fd7-courses.leclercdrive.fr/magasin-123111-123111-Montaudran",
                )
            )


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
    assert items[0]["store"] == "Auchan"
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


def test_auchan_parser_extracts_offering_contexts_from_fixture():
    import json
    from pathlib import Path

    fixture = Path(__file__).resolve().parent / "fixtures" / "auchan" / "offering_contexts.html"
    contexts = parse_auchan_offering_contexts(fixture.read_text(encoding="utf-8"))

    assert len(contexts) == 2
    drive = contexts[0]
    assert drive["pos_id"] == "aa33fa5e-98bd-4944-8576-86f10d7cb589"
    assert drive["pos_type"] == "DRIVE"
    assert drive["seller_id"] == "4c663296-54a8-45f6-b385-0be86b4dfe98"
    assert drive["store_reference"] == "6007"
    assert drive["channel"] == "PICK_UP"
    assert drive["name"] == "Auchan Drive Supermarché Toulouse Pontjumeaux"
    assert drive["address"] == "31000 Toulouse"
    assert drive["distance"] == "2.15 km"
    assert contexts[1]["seller_id"] == "a50ef74b-7bac-4bde-b138-cbfdbd4f6e01"


def test_auchan_parser_skips_cards_without_seller_form():
    html = """
    <div class="journey-offering-context__wrapper journeyPosItem"
         data-id="orphan" data-type="DRIVE">
      <span class="place-pos__name">Orphan</span>
    </div>
    """
    assert parse_auchan_offering_contexts(html) == []


def test_auchan_fetch_search_requires_selected_store(test_engine):
    async def run():
        with Session(test_engine) as session:
            return await fetch_search_results(
                store=SupermarketStore.AUCHAN,
                queries=["lait"],
                max_results=5,
                session=session,
            )

    import asyncio

    with pytest.raises(AuchanStoreSelectionError) as exc_info:
        asyncio.run(run())
    assert "Sélectionnez un magasin" in str(exc_info.value)


def test_auchan_fetch_search_uses_selected_store_context(test_engine, monkeypatch):
    import asyncio

    captured = {}

    async def fake_search_auchan(queries, max_results=10, sort_by=None, promotions_only=False, cookies=None, store_selection=None):
        captured["store_selection"] = store_selection
        return {
            "lait": [
                {
                    "id": "6baf949f-7d78-4d36-8458-3e96f5637688",
                    "name": "Lait demi-écrémé équitable UHT",
                    "price": "7,62 €",
                }
            ]
        }

    monkeypatch.setattr("app.services.store_catalog.search_auchan", fake_search_auchan)

    with Session(test_engine) as session:
        upsert_selected_store(
            session,
            SupermarketStore.AUCHAN,
            external_store_id="4c663296-54a8-45f6-b385-0be86b4dfe98",
            store_label="Auchan Drive Toulouse Pontjumeaux",
            raw_payload={
                "store_reference": "6007",
                "channel": "PICK_UP",
                "zipcode": "31400",
                "city": "Toulouse",
                "latitude": 43.604464,
                "longitude": 1.444243,
            },
        )

    async def run():
        with Session(test_engine) as session:
            return await fetch_search_results(
                store=SupermarketStore.AUCHAN,
                queries=["lait"],
                max_results=5,
                session=session,
            )

    results = asyncio.run(run())
    assert len(results) == 1
    assert results[0]["price_text"] == "7,62 €"

    selection = captured["store_selection"]
    assert isinstance(selection, AuchanStoreContext)
    assert selection.seller_id == "4c663296-54a8-45f6-b385-0be86b4dfe98"
    assert selection.store_reference == "6007"
    assert selection.zipcode == "31400"
    assert selection.latitude == 43.604464


def test_auchan_selected_store_endpoints_persist_and_read(client, auth_headers, monkeypatch, test_engine):
    async def fake_select_auchan_store(context, cookies=None):
        assert context.seller_id == "4c663296-54a8-45f6-b385-0be86b4dfe98"
        assert context.store_reference == "6007"
        return {"id": "cf9f3c53-f09b-44c2-ab45-c24debf45fe3", "activeContexts": []}

    monkeypatch.setattr(
        "app.services.scrapers.auchan.select_auchan_store",
        fake_select_auchan_store,
    )

    read_before = client.get("/api/v1/supermarket/auchan/selected-store", headers=auth_headers)
    assert read_before.status_code == 200
    assert read_before.json() is None

    payload = {
        "seller_id": "4c663296-54a8-45f6-b385-0be86b4dfe98",
        "store_reference": "6007",
        "channel": "PICK_UP",
        "store_label": "Auchan Drive Supermarché Toulouse Pontjumeaux",
        "location_label": "31400 Toulouse",
        "zipcode": "31400",
        "city": "Toulouse",
        "latitude": 43.604464,
        "longitude": 1.444243,
    }
    selected = client.post(
        "/api/v1/supermarket/auchan/selected-store",
        headers=auth_headers,
        json=payload,
    )
    assert selected.status_code == 200, selected.text
    body = selected.json()
    assert body["external_store_id"] == "4c663296-54a8-45f6-b385-0be86b4dfe98"
    assert body["store_label"] == "Auchan Drive Supermarché Toulouse Pontjumeaux"
    assert body["location_label"] == "31400 Toulouse"

    with Session(test_engine) as session:
        selection = get_selected_store(session, SupermarketStore.AUCHAN)
        assert selection is not None
        assert selection.raw_payload["store_reference"] == "6007"
        assert selection.raw_payload["journey_id"] == "cf9f3c53-f09b-44c2-ab45-c24debf45fe3"

    read_after = client.get("/api/v1/supermarket/auchan/selected-store", headers=auth_headers)
    assert read_after.status_code == 200
    assert read_after.json()["external_store_id"] == "4c663296-54a8-45f6-b385-0be86b4dfe98"


def test_auchan_offering_contexts_endpoint(client, auth_headers, monkeypatch):
    async def fake_list_auchan_offering_contexts(**kwargs):
        assert kwargs["zipcode"] == "31400"
        assert kwargs["city"] == "Toulouse"
        return [
            {
                "pos_id": "aa33fa5e-98bd-4944-8576-86f10d7cb589",
                "pos_type": "DRIVE",
                "seller_id": "4c663296-54a8-45f6-b385-0be86b4dfe98",
                "store_reference": "6007",
                "channel": "PICK_UP",
                "name": "Auchan Drive Supermarché Toulouse Pontjumeaux",
                "address": "31000 Toulouse",
                "distance": "2.15 km",
            }
        ]

    monkeypatch.setattr(
        "app.services.scrapers.auchan.list_auchan_offering_contexts",
        fake_list_auchan_offering_contexts,
    )

    response = client.get(
        "/api/v1/supermarket/auchan/offering-contexts",
        headers=auth_headers,
        params={"zipcode": "31400", "city": "Toulouse", "latitude": 43.604464, "longitude": 1.444243},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 1
    assert body[0]["seller_id"] == "4c663296-54a8-45f6-b385-0be86b4dfe98"
    assert body[0]["name"] == "Auchan Drive Supermarché Toulouse Pontjumeaux"


def test_auchan_search_endpoint_returns_400_without_selected_store(client, auth_headers):
    response = client.post(
        "/api/v1/supermarket/search",
        headers=auth_headers,
        json={"store": "auchan", "queries": ["lait"], "max_results": 5},
    )
    assert response.status_code == 400
    assert "Sélectionnez un magasin" in response.json()["detail"]


def test_geocode_auchan_address_uses_open_api_when_coords_missing(monkeypatch):
    import asyncio

    import httpx as real_httpx

    from app.services.scrapers import auchan as auchan_module

    def handler(request: real_httpx.Request) -> real_httpx.Response:
        return real_httpx.Response(
            200,
            json={"features": [{"geometry": {"coordinates": [1.47056, 43.589648]}}]},
        )

    class _MockClient(real_httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = real_httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(auchan_module.httpx, "AsyncClient", _MockClient)

    lat, lng = asyncio.run(auchan_module.geocode_auchan_address("31400", "Toulouse"))
    assert lat == 43.589648
    assert lng == 1.47056


def test_geocode_auchan_address_keeps_provided_coords(monkeypatch):
    import asyncio

    import httpx as real_httpx

    from app.services.scrapers import auchan as auchan_module

    def handler(request: real_httpx.Request) -> real_httpx.Response:
        raise AssertionError("should not call network when coords provided")

    class _MockClient(real_httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = real_httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(auchan_module.httpx, "AsyncClient", _MockClient)

    lat, lng = asyncio.run(auchan_module.geocode_auchan_address("31400", "Toulouse", 43.5, 1.4))
    assert lat == 43.5
    assert lng == 1.4


def test_geocode_auchan_address_returns_none_on_error(monkeypatch):
    import asyncio

    import httpx as real_httpx

    from app.services.scrapers import auchan as auchan_module

    def handler(request: real_httpx.Request) -> real_httpx.Response:
        raise real_httpx.ConnectError("boom")

    class _MockClient(real_httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = real_httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(auchan_module.httpx, "AsyncClient", _MockClient)

    assert asyncio.run(auchan_module.geocode_auchan_address("31400", "Toulouse")) == (None, None)


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
