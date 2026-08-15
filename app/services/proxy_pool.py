from __future__ import annotations

import os
import re
import threading
import time

DEFAULT_PROXIES_FILE = "data/proxies.txt"
DEFAULT_COOLDOWN_SECONDS = 600

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def parse_proxies(text: str) -> list[str]:
    """Parse raw proxies.txt content into normalized proxy URLs.

    One proxy per line as ``login:password@host:port``. Blank lines and
    ``#`` comments are ignored; a proxy without a scheme gets ``http://``
    prefixed.
    """
    proxies: list[str] = []
    for raw in text.splitlines():
        proxy = _normalize_line(raw)
        if proxy is not None:
            proxies.append(proxy)
    return proxies


def _normalize_line(raw: str) -> str | None:
    proxy = raw.strip()
    if not proxy or proxy.startswith("#"):
        return None
    if not _SCHEME_RE.match(proxy):
        proxy = f"http://{proxy}"
    return proxy


class ProxyPool:
    """Shared, in-memory pool of proxies with sticky scopes and cooldowns.

    ``acquire(scope)`` keeps the same proxy for a scope until it is marked
    blocked; blocked proxies cool down and the pool round-robins the healthy
    ones. Module-level state only — no persistence.
    """

    def __init__(self, proxies: list[str], cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS):
        self._proxies = list(proxies)
        self.cooldown_seconds = cooldown_seconds
        self._cursor = 0
        self._sticky: dict[str, str] = {}
        self._cooldown_until: dict[str, float] = {}
        self._lock = threading.Lock()

    @property
    def proxies(self) -> list[str]:
        return list(self._proxies)

    def __len__(self) -> int:
        return len(self._proxies)

    def acquire(self, scope: str) -> str | None:
        """Return a healthy proxy for a sticky session, or None when none is available."""
        with self._lock:
            now = time.monotonic()
            sticky = self._sticky.get(scope)
            if sticky is not None and self._available(sticky, now):
                return sticky
            total = len(self._proxies)
            if total == 0:
                self._sticky.pop(scope, None)
                return None
            for _ in range(total):
                candidate = self._proxies[self._cursor]
                self._cursor = (self._cursor + 1) % total
                if self._available(candidate, now):
                    self._sticky[scope] = candidate
                    return candidate
            self._sticky.pop(scope, None)
            return None

    def release(self, proxy: str, ok: bool) -> None:
        """Report a proxy outcome: ``ok=True`` re-enables it, ``ok=False`` starts its cooldown."""
        with self._lock:
            if ok:
                self._cooldown_until.pop(proxy, None)
            else:
                self._cooldown_until[proxy] = time.monotonic() + self.cooldown_seconds
                for scope in [s for s, assigned in self._sticky.items() if assigned == proxy]:
                    del self._sticky[scope]

    def _available(self, proxy: str, now: float) -> bool:
        return self._cooldown_until.get(proxy, 0.0) <= now


def load_proxies(file_path: str | None = None, cooldown_seconds: int | None = None) -> ProxyPool:
    """Load the proxy list (default ``data/proxies.txt``) into a shared pool.

    The file path comes from ``file_path``, else ``ADAMHUB_PROXIES_FILE``,
    else ``data/proxies.txt``. The cooldown comes from ``cooldown_seconds``,
    else ``ADAMHUB_PROXY_COOLDOWN_SECONDS``, else 600. A missing or empty
    file yields an empty pool — callers fall back to direct connections.
    """
    path = file_path or os.environ.get("ADAMHUB_PROXIES_FILE") or DEFAULT_PROXIES_FILE
    cooldown = _resolve_cooldown(cooldown_seconds)
    try:
        with open(path, encoding="utf-8") as handle:
            proxies = parse_proxies(handle.read())
    except FileNotFoundError:
        proxies = []
    return ProxyPool(proxies, cooldown)


def _resolve_cooldown(cooldown_seconds: int | None) -> int:
    if cooldown_seconds is not None:
        return cooldown_seconds
    raw = os.environ.get("ADAMHUB_PROXY_COOLDOWN_SECONDS")
    if raw is None:
        return DEFAULT_COOLDOWN_SECONDS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_COOLDOWN_SECONDS


_pool: ProxyPool | None = None


def get_pool() -> ProxyPool:
    global _pool
    if _pool is None:
        _pool = load_proxies()
    return _pool


def acquire(scope: str) -> str | None:
    """Acquire a proxy from the shared pool, sticky per scope."""
    return get_pool().acquire(scope)


def release(proxy: str, ok: bool) -> None:
    """Release a proxy from the shared pool: ``ok=True`` healthy, ``ok=False`` blocked."""
    get_pool().release(proxy, ok)
