from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import unicodedata
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup


CATEGORY_HINTS = {
    "agrumes": {
        "agrume",
        "agrumes",
        "orange",
        "oranges",
        "pamplemousse",
        "pamplemousses",
        "citron",
        "citrons",
        "clementine",
        "clementines",
        "mandarine",
        "mandarines",
    },
    "pommes": {"pomme", "pommes"},
    "multi fruits": {"multifruit", "multifruits"},
}


def extract_category_from_tracking_code(tracking_code: str | None) -> str | None:
    if not tracking_code:
        return None
    try:
        decoded = base64.b64decode(tracking_code + "===").decode("utf-8", "ignore")
    except Exception:
        return None

    family_markers = [
        "sous-famille",
        "sous-familles",
        "famille",
        "familles",
        "rayon",
        "rayons",
    ]
    lower = decoded.lower()
    for marker in family_markers:
        idx = lower.find(marker)
        if idx == -1:
            continue
        tail = decoded[idx: idx + 300]
        for stop_marker in [" pour la requête ", " dans la requête "]:
            stop_idx = tail.lower().find(stop_marker)
            if stop_idx != -1:
                tail = tail[:stop_idx]
                break
        labels = re.findall(r'"([^"]+)"', tail)
        labels = [label.strip() for label in labels if label.strip()]
        if labels:
            return " / ".join(dict.fromkeys(labels))
    return None


def normalize_category_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


def tokenize_category_text(value: str | None) -> set[str]:
    return {token for token in normalize_category_text(value).split() if len(token) > 2}


def build_filter_category_lookup(content: str) -> dict[int, str]:
    match = re.search(
        r'\\"type\\":\\"categories\\",\\"label\\":\\"categories\\",\\"values\\":\[(?P<values>.*?)\]\},\{\\"type\\":',
        content,
        re.DOTALL,
    )
    if not match:
        return {}

    return {
        int(category_id): label.strip()
        for category_id, label in re.findall(r'\\"id\\":(\d+),\\"label\\":\\"([^\\"]+)\\"', match.group("values"))
        if label.strip()
    }


def infer_category_from_name(name: str | None, filter_categories: dict[int, str]) -> str | None:
    name_tokens = tokenize_category_text(name)
    if not name_tokens:
        return None

    best_label: str | None = None
    best_score = 0
    second_score = 0
    for label in dict.fromkeys(filter_categories.values()):
        label_normalized = normalize_category_text(label)
        hint_tokens = set()
        for key, values in CATEGORY_HINTS.items():
            if key in label_normalized:
                hint_tokens.update(values)
        if not hint_tokens:
            continue

        hint_overlap = len(name_tokens & hint_tokens)
        exact_match = 1 if label_normalized and label_normalized in normalize_category_text(name) else 0
        score = hint_overlap * 2 + exact_match * 4
        if score > best_score:
            second_score = best_score
            best_score = score
            best_label = label
        elif score > second_score:
            second_score = score

    if best_score < 2 or best_score == second_score:
        return None
    return best_label


def extract_category_from_product_breadcrumb(content: str) -> str | None:
    soup = BeautifulSoup(content, "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw_json = script.string or script.get_text()
        if not raw_json:
            continue
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            continue

        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if not isinstance(candidate, dict) or candidate.get("@type") != "BreadcrumbList":
                continue
            items = candidate.get("itemListElement")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = (item.get("name") or "").strip()
                if name:
                    return name

    breadcrumb_nav = soup.find("nav", attrs={"aria-label": lambda value: value and "fil" in value.lower()})
    if not breadcrumb_nav:
        return None

    category_node = breadcrumb_nav.select_one("ol li button") or breadcrumb_nav.select_one("ol li a")
    if not category_node:
        return None

    category = category_node.get_text(" ", strip=True)
    return category or None


def build_product_category_lookup(content: str) -> dict[str, str]:
    filter_categories = build_filter_category_lookup(content)
    lookup: dict[str, str] = {}
    pattern = re.compile(
        r'\\"url\\":\\"(?P<url>/produit/[^\\"]+)\\".*?'
        r'\\"famillyId\\":(?P<family>\d+),\\"subFamillyId\\":(?P<subfamily>\d+),\\"departmentId\\":(?P<department>\d+),'
        r'\\"trackingCode\\":\\"(?P<tracking>[^\\"]+)\\"',
        re.DOTALL,
    )
    for match in pattern.finditer(content):
        product_url = f"https://www.intermarche.com{match.group('url').replace('\\/', '/')}"
        category = None
        for category_id in (
            int(match.group("subfamily")),
            int(match.group("family")),
            int(match.group("department")),
        ):
            category = filter_categories.get(category_id)
            if category:
                break
        if not category:
            category = extract_category_from_tracking_code(match.group("tracking"))
        if not category:
            category = infer_category_from_name(match.group("url"), filter_categories)
        if category:
            lookup[product_url] = category
    return lookup


async def fetch_product_breadcrumb_category(page, product_url: str) -> str | None:
    await page.goto(product_url, wait_until="domcontentloaded")
    try:
        await page.wait_for_load_state("load", timeout=10_000)
    except Exception:
        pass
    try:
        await page.wait_for_function(
            """
            () => {
              return Array.from(document.querySelectorAll("script[type='application/ld+json']"))
                .some((node) => node.textContent?.includes("BreadcrumbList"));
            }
            """,
            timeout=10_000,
        )
    except Exception:
        await asyncio.sleep(5)

    return extract_category_from_product_breadcrumb(await page.content())


async def hydrate_product_categories_from_detail_pages(context, items: list[dict[str, str | None]]) -> None:
    pending = [item for item in items if item.get("product_url")]
    if not pending:
        return

    detail_page = await context.new_page()
    try:
        for item in pending:
            try:
                category = await fetch_product_breadcrumb_category(detail_page, item["product_url"])
                if category:
                    item["category"] = category
            except Exception:
                continue
    finally:
        await detail_page.close()


def parse_intermarche_html(content: str, max_results: int = 10) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(content, "html.parser")
    category_lookup = build_product_category_lookup(content)
    items = soup.find_all("div", attrs={"data-testid": "product-layout"})
    if not items:
        items = soup.find_all("div", class_=lambda classes: classes and "productlayout" in classes.lower())

    results: list[dict[str, str | None]] = []
    for item in items[:max_results]:
        brand_elem = item.find("p", class_=lambda classes: classes and "font-bold" in classes and "font-open-sans" in classes)
        brand = brand_elem.get_text(strip=True) if brand_elem else None

        name_elem = item.find("h2", class_=lambda classes: classes and "title" in classes.lower())
        raw_name = name_elem.get_text(strip=True) if name_elem else "Produit inconnu"
        name = f"{brand} - {raw_name}" if brand and raw_name != "Produit inconnu" else raw_name

        price_elem = item.find("div", attrs={"data-testid": "default"})
        if not price_elem:
            price_elem = item.find("div", class_=lambda classes: classes and "price" in classes.lower())
        price = price_elem.get_text(strip=True) if price_elem else None

        packaging_elem = item.find("p", class_=lambda classes: classes and "packaging" in classes.lower())
        packaging = packaging_elem.get_text(strip=True) if packaging_elem else None

        img_elem = item.find("img", class_=lambda classes: classes and "image" in classes.lower()) or item.find("img")
        image_url = img_elem.get("src") if img_elem else None

        link_elem = item.find("a", class_=lambda classes: classes and "productcard__link" in classes.lower()) or item.find("a", href=True)
        href = link_elem.get("href") if link_elem else None
        external_id = href.rstrip("/").split("/")[-1] if href else None
        product_url = None
        if href:
            product_url = href if href.startswith("http") else f"https://www.intermarche.com{href}"
        category = category_lookup.get(product_url) if product_url else None

        results.append(
            {
                "id": external_id,
                "name": name,
                "brand": brand,
                "category": category,
                "packaging": packaging,
                "price": price,
                "image": image_url,
                "product_url": product_url,
                "store": "Intermarché",
            }
        )

    return results


def requires_intermarche_store_selection(content: str) -> bool:
    soup = BeautifulSoup(content, "html.parser")
    page_text = soup.get_text(" ", strip=True).lower()
    return (
        "sélectionner un magasin" in page_text
        or "selectionner un magasin" in page_text
        or "storelocatore.switchbtn.add-list" in page_text
    )


async def search_intermarche(
    queries: list[str],
    max_results: int = 10,
    sort_by: str | None = None,
    promotions_only: bool = False,
) -> dict[str, list[dict[str, str | None]]]:
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError as exc:
        raise RuntimeError(
            "Camoufox is required for live Intermarché scraping. "
            "Install the `camoufox[geoip]` package and run `python -m camoufox fetch`."
        ) from exc

    results: dict[str, list[dict[str, str | None]]] = {}

    async with AsyncCamoufox(
        headless=True,
        geoip=True,
        locale="fr-FR",
        os="macos",
    ) as browser:
        context = await browser.new_context(locale="fr-FR", timezone_id="Europe/Paris")
        cookies_path = Path(__file__).resolve().parents[3] / "data" / "cookies_intermarche.json"
        if cookies_path.exists():
            with cookies_path.open("r", encoding="utf-8") as handle:
                raw_cookies = json.load(handle)
            sanitized = []
            for cookie in raw_cookies:
                same_site = cookie.get("sameSite")
                if same_site == "lax":
                    cookie["sameSite"] = "Lax"
                elif same_site == "strict":
                    cookie["sameSite"] = "Strict"
                elif same_site in {"none", "no_restriction"}:
                    cookie["sameSite"] = "None"
                elif same_site is None and "sameSite" in cookie:
                    del cookie["sameSite"]
                sanitized.append(cookie)
            await context.add_cookies(sanitized)

        page = await context.new_page()
        await page.goto("https://www.intermarche.com/", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        try:
            accept_button = await page.wait_for_selector("button#agree", timeout=3_000)
            if accept_button:
                await accept_button.click()
        except Exception:
            pass

        sort_map = {
            "prix_croissant": "Prix croissant",
            "prix_decroissant": "Prix décroissant",
            "prix_kg_croissant": "Prix/kg ou prix/l croissant",
            "prix_kg_decroissant": "Prix/kg ou prix/l décroissant",
        }

        for query in queries:
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.intermarche.com/recherche/{encoded_query}"
            await page.goto(search_url, wait_until="domcontentloaded")
            await asyncio.sleep(4)

            if promotions_only:
                try:
                    promo_p = page.locator('p:has-text("Promotions")')
                    if await promo_p.count() > 0:
                        promo_switch = promo_p.first.locator('xpath=../../..//input[@role="switch"]')
                        if await promo_switch.count() > 0:
                            await promo_switch.first.click(force=True)
                            await asyncio.sleep(2)
                except Exception:
                    pass

            if sort_by:
                sort_text = sort_map.get(sort_by, "Pertinence")
                try:
                    sort_button = page.locator("button#stime-select-button")
                    if await sort_button.count() > 0:
                        await sort_button.first.click()
                        await asyncio.sleep(1)
                        sort_option = page.locator(f'text="{sort_text}"')
                        if await sort_option.count() > 0:
                            await sort_option.first.click()
                            await asyncio.sleep(2)
                        else:
                            await page.keyboard.press("Escape")
                except Exception:
                    pass

            content = await page.content()
            dump_path = Path(__file__).resolve().parents[3] / "output" / "intermarche_results.html"
            dump_path.parent.mkdir(parents=True, exist_ok=True)
            dump_path.write_text(content, encoding="utf-8")
            if requires_intermarche_store_selection(content):
                raise RuntimeError(
                    "Intermarché requires a selected store before search results can load. "
                    "Provide a valid `data/cookies_intermarche.json` file in the runtime image."
                )
            query_results = parse_intermarche_html(content, max_results=max_results)
            await hydrate_product_categories_from_detail_pages(context, query_results)
            results[query] = query_results

        await context.close()

    return results


if __name__ == "__main__":
    html_path = os.environ.get("INTERMARCHE_HTML_PATH")
    if html_path:
        print(json.dumps(parse_intermarche_html(Path(html_path).read_text(encoding="utf-8")), indent=2, ensure_ascii=False))
