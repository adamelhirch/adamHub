"""Proof script — GET /s?q=lait on carrefour.fr with real cookies + proxy pool.

Usage:
    uv run python scripts/prove_carrefour_cf.py [httpx|curl_cffi|httpx_proxy|curl_proxy]

Tests, in the order of the task:
  1) curl_cffi impersonation chrome            -> curl_cffi
  2) residential proxy from pool (sticky)      -> httpx_proxy
  3) combination of both                       -> curl_proxy
Baseline (current code, direct, no proxy)     -> httpx
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COOKIES_PATH = ROOT / "data" / "cookies_carrefour.json"
PROXIES_PATH = ROOT / "data" / "proxies.txt"

BASE_URL = "https://www.carrefour.fr"

CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
)


def load_cookies() -> list[dict[str, Any]]:
    if not COOKIES_PATH.exists():
        print("!! no cookies file", COOKIES_PATH)
        return []
    return json.loads(COOKIES_PATH.read_text(encoding="utf-8"))


def load_proxy() -> str | None:
    if not PROXIES_PATH.exists():
        print("!! no proxies file", PROXIES_PATH)
        return None
    for raw in PROXIES_PATH.read_text(encoding="utf-8").splitlines():
        proxy = raw.strip()
        if not proxy or proxy.startswith("#"):
            continue
        if not proxy.startswith("http"):
            proxy = f"http://{proxy}"
        return proxy
    return None


def build_headers() -> dict[str, str]:
    return {
        "User-Agent": CHROME_UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "fr,en;q=0.9",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/",
        "priority": "u=1, i",
        "sec-ch-ua": '"Chromium";v="147", "Not.A/Brand";v="8"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "sec-fetch-dest": "empty",
        "x-requested-with": "XMLHttpRequest",
    }


def describe(status: int, text: str, elapsed: float) -> None:
    snippet = text[:200].replace("\n", " ")
    print(f"  status={status} elapsed={elapsed:.2f}s body[:200]={snippet!r}")


async def run_httpx(proxy: str | None) -> None:
    import httpx

    cookies = load_cookies()
    jar = httpx.Cookies()
    for c in cookies:
        if c.get("name") and c.get("value") is not None:
            jar.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))

    client_kwargs: dict[str, Any] = {
        "base_url": BASE_URL,
        "cookies": jar,
        "timeout": httpx.Timeout(30.0),
        "follow_redirects": False,
    }
    if proxy:
        client_kwargs["proxy"] = proxy
        client_kwargs["trust_env"] = False
    async with httpx.AsyncClient(**client_kwargs) as client:
        t0 = asyncio.get_event_loop().time()
        r = await client.get("/s", params={"q": "lait"}, headers=build_headers())
        elapsed = asyncio.get_event_loop().time() - t0
    describe(r.status_code, r.text, elapsed)
    print(f"  content-type={r.headers.get('content-type')}")


async def run_curl_cffi(proxy: str | None) -> None:
    from curl_cffi.requests import AsyncSession
    from curl_cffi.requests.cookies import Cookies

    cookies = load_cookies()
    jar = Cookies()
    for c in cookies:
        if c.get("name") and c.get("value") is not None:
            jar.set(c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/"))

    session_kwargs: dict[str, Any] = {
        "impersonate": "chrome",
        "cookies": jar,
        "timeout": 30.0,
    }
    if proxy:
        session_kwargs["proxies"] = {"http": proxy, "https": proxy}

    s = AsyncSession(**session_kwargs)
    try:
        t0 = asyncio.get_event_loop().time()
        r = await s.get(
            f"{BASE_URL}/s", params={"q": "lait"}, headers=build_headers()
        )
        elapsed = asyncio.get_event_loop().time() - t0
        describe(r.status_code, r.text, elapsed)
        print(f"  content-type={r.headers.get('content-type')}")
    finally:
        await s.close()


async def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "httpx"
    proxy = load_proxy()
    print(f"mode={mode} proxy={'yes' if proxy else 'no'}")
    if mode == "httpx":
        await run_httpx(None)
    elif mode == "httpx_proxy":
        await run_httpx(proxy)
    elif mode == "curl_cffi":
        await run_curl_cffi(None)
    elif mode == "curl_proxy":
        await run_curl_cffi(proxy)
    else:
        print(f"unknown mode {mode}")


if __name__ == "__main__":
    asyncio.run(main())
