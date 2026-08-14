from __future__ import annotations

_UNIT_BASE: dict[str, tuple[str, float]] = {
    "kg": ("g", 1000.0),
    "g": ("g", 1.0),
    "l": ("ml", 1000.0),
    "ml": ("ml", 1.0),
}


def normalize_name(value: str | None) -> str:
    """Collapse whitespace and case so equivalent names compare equal."""
    return " ".join((value or "").strip().lower().split())


def unit_meta(unit: str | None) -> tuple[str, float]:
    """Return (base_unit, factor) for a unit, or (unit, 1.0) when unknown."""
    normalized_unit = unit.strip().lower() if unit else "item"
    base = _UNIT_BASE.get(normalized_unit)
    if not base:
        return normalized_unit, 1.0
    base_unit, factor = base
    return base_unit, factor


def to_base(quantity: float, unit: str | None) -> tuple[float, str]:
    """Convert a quantity into its base unit so different units compare equal.

    Unknown units pass through untouched: ``(quantity, normalized_unit)``.
    """
    normalized_unit = unit.strip().lower() if unit else "item"
    base = _UNIT_BASE.get(normalized_unit)
    if not base:
        return quantity, normalized_unit
    base_unit, factor = base
    return quantity * factor, base_unit


def from_base(quantity: float, unit: str | None) -> float:
    """Convert a base-unit quantity back into the given unit."""
    _, factor = unit_meta(unit)
    if factor == 0:
        return quantity
    return quantity / factor
