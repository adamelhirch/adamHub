from __future__ import annotations

from typing import Any

import httpx


NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
USER_AGENT = "AdamHUB/1.0 (personal hub; contact: leo@vanilledesire.com)"


class GeocoderError(RuntimeError):
    pass


def _format_title(address: dict[str, Any]) -> str:
    """Compose a short title from Nominatim address parts (e.g. '12 rue Foo')."""
    house_number = address.get("house_number") or ""
    road = address.get("road") or address.get("pedestrian") or address.get("cycleway") or ""
    if house_number and road:
        return f"{house_number} {road}".strip()
    return road or address.get("suburb") or address.get("city") or address.get("town") or ""


def _format_subtitle(address: dict[str, Any]) -> str:
    parts = [
        address.get("postcode"),
        address.get("city") or address.get("town") or address.get("village") or address.get("municipality"),
        address.get("country"),
    ]
    return ", ".join(part for part in parts if part)


async def search_addresses(query: str, limit: int = 6) -> list[dict[str, Any]]:
    """Search addresses via Nominatim. Returns a normalized list of candidates."""
    query = query.strip()
    if not query:
        return []

    params = {
        "q": query,
        "format": "json",
        "addressdetails": "1",
        "limit": str(limit),
        "accept-language": "fr",
    }
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "fr-FR,fr;q=0.9"}

    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
        response = await client.get(f"{NOMINATIM_BASE_URL}/search", params=params, headers=headers)
        if response.status_code >= 500:
            raise GeocoderError(f"Nominatim server error: {response.status_code}")
        response.raise_for_status()
        raw = response.json()

    results: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            latitude = float(item["lat"])
            longitude = float(item["lon"])
        except (KeyError, TypeError, ValueError):
            continue

        address = item.get("address") or {}
        title = _format_title(address) or item.get("display_name", "").split(",")[0]
        subtitle = _format_subtitle(address)
        results.append(
            {
                "title": title.strip(),
                "subtitle": subtitle,
                "formatted_address": item.get("display_name") or f"{title}, {subtitle}".strip(", "),
                "latitude": latitude,
                "longitude": longitude,
                "reference": str(item.get("place_id") or ""),
                "reference_type": "OSM_NOMINATIM",
            }
        )
    return results
