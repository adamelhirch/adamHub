#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import http.cookiejar
import json
import os
import platform
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_QUERY = "lait"
DEFAULT_TIMEOUT = 30
DEFAULT_BROWSER_WAIT_MS = 4000
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


def parse_args() -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parents[1]
    default_cookies = repo_root / "data" / "cookies_intermarche.json"
    default_api_base = os.environ.get("ADAMHUB_TEST_API_BASE_URL", "").strip()
    default_api_key = (
        os.environ.get("ADAMHUB_API_KEY", "").strip()
        or os.environ.get("VITE_API_KEY", "").strip()
    )

    parser = argparse.ArgumentParser(
        description=(
            "Teste Intermarche en acces direct puis, en option, "
            "l'API AdamHUB pour comparer Mac et VPS."
        )
    )
    parser.add_argument("--query", default=DEFAULT_QUERY, help="Requete Intermarche a tester.")
    parser.add_argument(
        "--cookies",
        type=Path,
        default=default_cookies,
        help="Chemin du fichier cookies_intermarche.json.",
    )
    parser.add_argument(
        "--search-url-template",
        default="https://www.intermarche.com/recherche/{query}",
        help="Template d'URL pour la recherche directe.",
    )
    parser.add_argument(
        "--api-base-url",
        default=default_api_base,
        help="Base URL API AdamHUB, ex: http://127.0.0.1:8000/api/v1",
    )
    parser.add_argument(
        "--api-key",
        default=default_api_key,
        help="API key AdamHUB. Par defaut: ADAMHUB_API_KEY ou VITE_API_KEY.",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=30,
        help="Nombre max de resultats pour le POST API.",
    )
    parser.add_argument(
        "--promotions-only",
        action="store_true",
        help="Teste aussi le mode promotions_only sur le POST API.",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Ne teste pas l'API AdamHUB, seulement Intermarche en direct.",
    )
    parser.add_argument(
        "--browser",
        choices=("none", "chromium", "camoufox", "all"),
        default="none",
        help="Ajoute un test navigateur headless.",
    )
    parser.add_argument(
        "--browser-wait-ms",
        type=int,
        default=DEFAULT_BROWSER_WAIT_MS,
        help="Temps d'attente apres chargement de la page navigateur.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Timeout reseau en secondes.",
    )
    return parser.parse_args()


def print_header(title: str) -> None:
    print(f"\n=== {title} ===")


def print_result(name: str, ok: bool, detail: str) -> None:
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")


def machine_summary() -> str:
    return (
        f"host={socket.gethostname()} "
        f"platform={platform.system()} {platform.release()} "
        f"python={platform.python_version()}"
    )


def load_cookies(cookie_path: Path) -> list[dict[str, Any]]:
    if not cookie_path.exists():
        raise FileNotFoundError(f"Fichier absent: {cookie_path}")

    payload = json.loads(cookie_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Le fichier cookies doit contenir une liste JSON.")

    cookies: list[dict[str, Any]] = []
    now = time.time()
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        domain = str(item.get("domain") or "")
        expires = item.get("expirationDate", item.get("expires"))
        if not name or value is None:
            continue
        if expires is not None:
            try:
                if float(expires) < now:
                    continue
            except (TypeError, ValueError):
                pass
        cookies.append(item)

    if not cookies:
        raise ValueError("Aucun cookie Intermarche exploitable trouve dans le fichier.")

    return cookies


def detect_datadome(content: str) -> bool:
    lowered = content.lower()
    return (
        "geo.captcha-delivery.com/interstitial" in lowered
        or "captcha-delivery.com/interstitial" in lowered
        or "datadome device check" in lowered
    )


def detect_store_selection(content: str) -> bool:
    lowered = content.lower()
    return (
        "selectionner un magasin" in lowered
        or "selectionnez un magasin" in lowered
        or "sélectionner un magasin" in lowered
        or "sélectionnez un magasin" in lowered
    )


def count_product_cards(content: str) -> int:
    patterns = [
        r'data-testid=["\']product-layout["\']',
        r'productlayout',
        r'product-card',
    ]
    counts = [len(re.findall(pattern, content, flags=re.IGNORECASE)) for pattern in patterns]
    return max(counts) if counts else 0


def build_cookie_jar(raw_cookies: list[dict[str, Any]]) -> http.cookiejar.CookieJar:
    jar = http.cookiejar.CookieJar()
    for item in raw_cookies:
        name = item.get("name")
        value = item.get("value")
        domain = str(item.get("domain") or "")
        path = str(item.get("path") or "/")
        if not name or value is None:
            continue

        expires = item.get("expirationDate", item.get("expires"))
        try:
            expires_value = int(float(expires)) if expires is not None else None
        except (TypeError, ValueError):
            expires_value = None

        domain_specified = bool(domain)
        domain_initial_dot = domain.startswith(".")
        cookie = http.cookiejar.Cookie(
            version=0,
            name=name,
            value=str(value),
            port=None,
            port_specified=False,
            domain=domain,
            domain_specified=domain_specified,
            domain_initial_dot=domain_initial_dot,
            path=path,
            path_specified=True,
            secure=bool(item.get("secure", False)),
            expires=expires_value,
            discard=False,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False,
        )
        jar.set_cookie(cookie)
    return jar


def build_playwright_cookies(raw_cookies: list[dict[str, Any]], base_url: str) -> list[dict[str, Any]]:
    parsed_base = urllib.parse.urlparse(base_url)
    origin = f"{parsed_base.scheme}://{parsed_base.netloc}"
    cookies: list[dict[str, Any]] = []
    for item in raw_cookies:
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue

        cookie: dict[str, Any] = {
            "name": str(name),
            "value": str(value),
            "path": str(item.get("path") or "/"),
            "httpOnly": bool(item.get("httpOnly", False)),
            "secure": bool(item.get("secure", False)),
        }

        domain = str(item.get("domain") or "")
        if domain:
            cookie["domain"] = domain
        else:
            cookie["url"] = origin

        expires = item.get("expirationDate", item.get("expires"))
        if expires is not None:
            try:
                cookie["expires"] = int(float(expires))
            except (TypeError, ValueError):
                pass

        same_site = str(item.get("sameSite") or "").lower()
        if same_site == "lax":
            cookie["sameSite"] = "Lax"
        elif same_site == "strict":
            cookie["sameSite"] = "Strict"
        elif same_site in {"none", "no_restriction"}:
            cookie["sameSite"] = "None"

        cookies.append(cookie)
    return cookies


def make_request(
    url: str,
    timeout: int,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    method: str | None = None,
    cookies: list[dict[str, Any]] | None = None,
) -> tuple[int, str]:
    request = urllib.request.Request(url=url, data=body, headers=headers or {}, method=method)
    context = ssl.create_default_context()
    handlers: list[Any] = [urllib.request.HTTPSHandler(context=context)]
    if cookies:
        handlers.append(urllib.request.HTTPCookieProcessor(build_cookie_jar(cookies)))
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
            charset = response.headers.get_content_charset() or "utf-8"
            return response.status, raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        charset = exc.headers.get_content_charset() or "utf-8"
        return exc.code, raw.decode(charset, errors="replace")


def run_direct_intermarche_test(args: argparse.Namespace, cookies: list[dict[str, Any]]) -> bool:
    print_header("Intermarche Direct")
    encoded_query = urllib.parse.quote(args.query)
    url = args.search_url_template.format(query=encoded_query)
    status, body = make_request(
        url=url,
        timeout=args.timeout,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
        method="GET",
        cookies=cookies,
    )

    datadome = detect_datadome(body)
    store_selection = detect_store_selection(body)
    product_count = count_product_cards(body)
    ok = status == 200 and not datadome and not store_selection and product_count > 0
    detail = (
        f"status={status} products={product_count} "
        f"datadome={'yes' if datadome else 'no'} "
        f"store_selection={'yes' if store_selection else 'no'} "
        f"url={url}"
    )
    print_result("intermarche_http", ok, detail)
    return ok


def summarize_page_result(url: str, content: str, *, status: int | None = None) -> tuple[bool, str]:
    datadome = detect_datadome(content)
    store_selection = detect_store_selection(content)
    product_count = count_product_cards(content)
    ok = (status in {None, 200}) and not datadome and not store_selection and product_count > 0
    detail = (
        f"status={status if status is not None else 'n/a'} products={product_count} "
        f"datadome={'yes' if datadome else 'no'} "
        f"store_selection={'yes' if store_selection else 'no'} "
        f"url={url}"
    )
    return ok, detail


async def run_browser_test_with_playwright(
    engine: str,
    url: str,
    cookies: list[dict[str, Any]],
    timeout_ms: int,
    wait_ms: int,
) -> tuple[bool, str]:
    try:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import async_playwright
    except ImportError as exc:
        return False, f"module manquant: {exc}"

    try:
        async with async_playwright() as pw:
            browser_type = getattr(pw, engine)
            browser = await browser_type.launch(headless=True)
            context = await browser.new_context(
                locale="fr-FR",
                timezone_id="Europe/Paris",
                user_agent=DEFAULT_USER_AGENT,
            )
            if cookies:
                await context.add_cookies(build_playwright_cookies(cookies, url))
            page = await context.new_page()
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(wait_ms)
            content = await page.content()
            await context.close()
            await browser.close()
            status = response.status if response else None
            return summarize_page_result(url, content, status=status)
    except PlaywrightError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)


async def run_browser_test_with_camoufox(
    url: str,
    cookies: list[dict[str, Any]],
    timeout_ms: int,
    wait_ms: int,
) -> tuple[bool, str]:
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError as exc:
        return False, f"module manquant: {exc}"

    try:
        async with AsyncCamoufox(
            headless=True,
            geoip=True,
            locale="fr-FR",
            os="macos",
        ) as browser:
            context = await browser.new_context(locale="fr-FR", timezone_id="Europe/Paris")
            if cookies:
                await context.add_cookies(build_playwright_cookies(cookies, url))
            page = await context.new_page()
            response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            await page.wait_for_timeout(wait_ms)
            content = await page.content()
            await context.close()
            status = response.status if response else None
            return summarize_page_result(url, content, status=status)
    except Exception as exc:
        return False, str(exc)


async def run_browser_tests(args: argparse.Namespace, cookies: list[dict[str, Any]]) -> None:
    if args.browser == "none":
        return

    print_header("Browser Headless")
    encoded_query = urllib.parse.quote(args.query)
    url = args.search_url_template.format(query=encoded_query)
    timeout_ms = args.timeout * 1000

    if args.browser in {"chromium", "all"}:
        ok, detail = await run_browser_test_with_playwright(
            engine="chromium",
            url=url,
            cookies=cookies,
            timeout_ms=timeout_ms,
            wait_ms=args.browser_wait_ms,
        )
        print_result("browser_chromium", ok, detail)

    if args.browser in {"camoufox", "all"}:
        ok, detail = await run_browser_test_with_camoufox(
            url=url,
            cookies=cookies,
            timeout_ms=timeout_ms,
            wait_ms=args.browser_wait_ms,
        )
        print_result("browser_camoufox", ok, detail)


def parse_json_body(body: str) -> Any:
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def summarize_api_body(body: str) -> str:
    parsed = parse_json_body(body)
    if isinstance(parsed, dict) and "detail" in parsed:
        return f"detail={parsed['detail']!r}"
    if isinstance(parsed, list):
        return f"items={len(parsed)}"
    if parsed is not None:
        preview = json.dumps(parsed, ensure_ascii=True)[:300]
        return f"json={preview}"
    compact = " ".join(body.split())
    return f"body={compact[:300]!r}"


def run_api_get_test(args: argparse.Namespace) -> bool:
    base = args.api_base_url.rstrip("/")
    url = (
        f"{base}/supermarket/search?"
        f"store=intermarche&query={urllib.parse.quote(args.query)}&limit={args.max_results}"
    )
    status, body = make_request(
        url=url,
        timeout=args.timeout,
        headers={
            "Accept": "application/json",
            "X-API-Key": args.api_key,
        },
        method="GET",
    )
    ok = status == 200
    print_result("api_get_cached", ok, f"status={status} {summarize_api_body(body)}")
    return ok


def run_api_post_test(args: argparse.Namespace, promotions_only: bool) -> bool:
    base = args.api_base_url.rstrip("/")
    url = f"{base}/supermarket/search"
    payload = {
        "store": "intermarche",
        "queries": [args.query],
        "max_results": args.max_results,
        "promotions_only": promotions_only,
    }
    status, body = make_request(
        url=url,
        timeout=args.timeout,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-Key": args.api_key,
        },
        body=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    suffix = "promotions" if promotions_only else "plain"
    ok = status == 200
    print_result(f"api_post_{suffix}", ok, f"status={status} {summarize_api_body(body)}")
    return ok


def run_api_tests(args: argparse.Namespace) -> None:
    print_header("AdamHUB API")
    if not args.api_base_url:
        print_result("api", False, "Aucune api-base-url fournie.")
        return
    if not args.api_key:
        print_result("api", False, "Aucune api-key fournie.")
        return

    run_api_get_test(args)
    run_api_post_test(args, promotions_only=False)
    if args.promotions_only:
        run_api_post_test(args, promotions_only=True)


def main() -> int:
    args = parse_args()

    print_header("Environment")
    print(machine_summary())

    try:
        cookies = load_cookies(args.cookies)
        print_result("cookies", True, f"path={args.cookies} count={len(cookies)}")
    except Exception as exc:
        print_result("cookies", False, str(exc))
        return 1

    run_direct_intermarche_test(args, cookies)
    asyncio.run(run_browser_tests(args, cookies))

    if not args.skip_api:
        run_api_tests(args)

    print(
        "\nInterprete le resultat comme suit:\n"
        "- HTTP direct OK + API POST KO sur le VPS => probleme de conteneur/deploiement AdamHUB.\n"
        "- HTTP direct KO seulement sur le VPS => probleme d'IP VPS, de cookies, ou de session Intermarche.\n"
        "- HTTP direct KO partout => cookies invalides ou magasin non selectionne."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
