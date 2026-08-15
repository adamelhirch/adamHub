from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.services import proxy_pool


class ProxySession:
    """Binds one search scope to a sticky pool proxy and its httpx client.

    Acquires a proxy from the shared pool for the whole search (sticky per
    scope), builds the httpx client through the given ``build_client`` factory,
    and releases the proxy when the search finishes. On a blocked signal (403,
    DataDome, timeout) callers ``rotate()``: the current proxy is released as
    failed (cooldown) and a fresh healthy one is acquired. An empty pool yields
    ``proxy is None`` — the client runs direct, no error.
    """

    def __init__(self, scope: str, build_client: Callable[[str | None], Any]):
        self._scope = scope
        self._build_client = build_client
        self.proxy = proxy_pool.acquire(scope)
        self.client = build_client(self.proxy)

    def release(self, ok: bool) -> None:
        """Report the outcome: ``ok=True`` healthy, ``ok=False`` blocked."""
        if self.proxy:
            proxy_pool.release(self.proxy, ok=ok)

    async def rotate(self) -> None:
        """Mark the current proxy blocked, acquire the next one and rebuild the client."""
        if self.proxy:
            proxy_pool.release(self.proxy, ok=False)
        previous = self.client
        self.proxy = proxy_pool.acquire(self._scope)
        self.client = self._build_client(self.proxy)
        if previous is not None:
            await _aclose(previous)

    async def aclose(self) -> None:
        if self.client is not None:
            await _aclose(self.client)
            self.client = None


async def _aclose(client: Any) -> None:
    close = getattr(client, "aclose", None)
    if close is not None:
        await close()
