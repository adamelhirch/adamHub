from __future__ import annotations

import json
import urllib.parse

from app.services.scrapers import ubereats


def _loc_cookie(payload: dict) -> dict:
    return {
        "name": ubereats.UBEREATS_LOC_COOKIE_NAME,
        "value": urllib.parse.quote(json.dumps(payload), safe=""),
        "domain": ".ubereats.com",
    }


def test_decode_uev2_loc_round_trip():
    payload = {
        "address": {
            "title": "Domicile",
            "subtitle": "Paris 11e",
            "eaterFormattedAddress": "23 rue de la Roquette, 75011 Paris",
        },
        "latitude": 48.8566,
        "longitude": 2.3522,
        "reference": "ChIJabc",
        "referenceType": "GOOGLE_PLACES",
    }
    cookies = [_loc_cookie(payload)]

    decoded = ubereats.decode_uev2_loc(cookies)
    assert decoded == payload
    assert ubereats.get_current_address_label(cookies) == (
        "Domicile — 23 rue de la Roquette, 75011 Paris"
    )


def test_update_uev2_loc_inserts_when_missing():
    cookies: list[dict] = []
    new_payload = {"address": {"title": "Bureau"}, "latitude": 48.85, "longitude": 2.35}
    ubereats.update_uev2_loc(cookies, new_payload)

    assert len(cookies) == 1
    assert cookies[0]["name"] == ubereats.UBEREATS_LOC_COOKIE_NAME
    assert ubereats.decode_uev2_loc(cookies) == new_payload


def test_parse_grocery_stores_filters_non_grocery():
    payload = {
        "data": {
            "feedItems": [
                {
                    "type": "REGULAR_STORE",
                    "store": {
                        "storeUuid": "store-1",
                        "title": {"text": "Carrefour City"},
                        "actionUrl": "/store/carrefour-city/abc?diningMode=DELIVERY",
                        "image": {"items": [{"url": "https://img.test/carrefour.png"}]},
                        "rating": {"text": "4.5"},
                        "meta": [{"badgeType": "ETD", "text": "10 min"}],
                    },
                },
                {
                    "type": "REGULAR_STORE",
                    "store": {
                        "storeUuid": "resto-1",
                        "title": {"text": "Pizza Roma"},
                    },
                },
                {
                    "type": "REGULAR_STORE",
                    "store": {
                        "storeUuid": "store-2",
                        "title": {"text": "Monoprix"},
                        "actionUrl": "/store/monoprix/def",
                    },
                },
                {
                    "type": "STORE_WITH_INLINE_ITEMS",
                    "store": {
                        "storeUuid": "store-3",
                        "title": {"text": "Picard"},
                    },
                },
                {
                    "type": "BANNER",
                    "store": {"storeUuid": "ignored", "title": {"text": "Carrefour Ad"}},
                },
            ]
        }
    }
    stores = ubereats.parse_grocery_stores(payload)
    uuids = {s["uuid"] for s in stores}
    assert uuids == {"store-1", "store-2", "store-3"}

    carrefour = next(s for s in stores if s["uuid"] == "store-1")
    assert carrefour["name"] == "Carrefour City"
    assert carrefour["image_url"] == "https://img.test/carrefour.png"
    assert carrefour["rating"] == 4.5
    assert carrefour["subtitle"] == "10 min"
    assert carrefour["address"] == "https://www.ubereats.com/store/carrefour-city/abc?diningMode=DELIVERY"


def _catalog_section(section_uuid: str, items: list[dict]) -> dict:
    return {
        "data": {
            "catalogSectionsMap": {
                section_uuid: [
                    {
                        "type": "STANDARD_ITEMS_PAYLOAD",
                        "catalogSectionUUID": section_uuid,
                        "payload": {
                            "standardItemsPayload": {"catalogItems": items},
                        },
                    }
                ]
            }
        }
    }


def _item(uuid_: str, title: str, price_cents: int | None, **extras) -> dict:
    base = {
        "uuid": uuid_,
        "title": title,
        "isAvailable": True,
        "isSoldOut": False,
        "imageUrl": extras.get("imageUrl"),
        "sectionUuid": extras.get("sectionUuid", "sec-1"),
        "subsectionUuid": extras.get("subsectionUuid", "sub-1"),
    }
    if price_cents is not None:
        base["purchaseInfo"] = {
            "purchaseOptions": [
                {"purchasePriceV2": {"base": {"low": price_cents}, "exponent": -2}}
            ]
        }
    if "priceTagline" in extras:
        base["priceTagline"] = extras["priceTagline"]
    return base


def test_parse_search_results_extracts_price_and_image():
    payload = _catalog_section(
        "sec-1",
        [
            _item("item-1", "Banane bio (1 kg)", 249, imageUrl="https://img.test/banane.png"),
            _item("item-2", "Lait demi-écrémé", 129, priceTagline={"text": "€1.29"}),
            _item("unavailable", "Article rupture", 199) | {"isAvailable": False},
        ],
    )
    items = ubereats.parse_search_results(payload, max_results=5, store_uuid="store-1")
    ids = [item["id"] for item in items]
    assert ids == ["item-1", "item-2"]
    assert items[0]["price_cents"] == 249
    assert items[0]["price"] == "2,49 €"
    assert items[0]["image"] == "https://img.test/banane.png"
    assert items[1]["price"] == "€1.29"
    assert items[1]["price_cents"] == 129


def test_parse_search_results_skips_sold_out():
    payload = _catalog_section(
        "sec-1",
        [
            _item("ok", "Pain", 199),
            _item("gone", "Pain rare", 299) | {"isSoldOut": True},
        ],
    )
    items = ubereats.parse_search_results(payload, max_results=10, store_uuid="store-1")
    assert [i["id"] for i in items] == ["ok"]


def test_parse_search_results_respects_max_results():
    payload = _catalog_section(
        "sec-1",
        [_item(f"item-{i}", f"Produit {i}", 100 + i) for i in range(1, 11)],
    )
    items = ubereats.parse_search_results(payload, max_results=3, store_uuid="store-1")
    assert len(items) == 3
