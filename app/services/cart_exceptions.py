"""Shared exception hierarchy for supermarket cart mirror operations."""

from __future__ import annotations


class SupermarketCartError(RuntimeError):
    """Base exception for supermarket cart operations."""


class SupermarketCartAuthError(SupermarketCartError):
    """Authentication failed or session expired with retailer."""


class SupermarketCartStoreContextError(SupermarketCartError):
    """Store Drive or branch context missing or invalid."""


class SupermarketCartNotFoundError(SupermarketCartError):
    """Cart or item was not found on remote retailer platform."""


class SupermarketCartConflictError(SupermarketCartError):
    """Cart concurrency or synchronization conflict."""
