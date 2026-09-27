from __future__ import annotations

import re
import unicodedata

_UNIT_BASE: dict[str, tuple[str, float]] = {
    "kg": ("g", 1000.0),
    "g": ("g", 1.0),
    "mg": ("g", 0.001),
    "l": ("ml", 1000.0),
    "cl": ("ml", 10.0),
    "dl": ("ml", 100.0),
    "ml": ("ml", 1.0),
}

_STEM_EXCLUDE_SUFFIXES = ("eau", "eux", "ois", "ais", "us", "as", "os", "is")

CUT_PREFIXES: list[tuple[str, str]] = [
    ("pavés de ", "pavés"),
    ("pavé de ", "pavé"),
    ("paves de ", "pavés"),
    ("pave de ", "pavé"),
    ("filets de ", "filets"),
    ("filet de ", "filet"),
    ("blancs de ", "blancs"),
    ("blanc de ", "blanc"),
    ("tranches de ", "tranches"),
    ("tranche de ", "tranche"),
    ("morceaux de ", "morceaux"),
    ("morceau de ", "morceau"),
    ("dés de ", "dés"),
    ("dé de ", "dés"),
    ("des de ", "dés"),
    ("de de ", "dés"),
    ("gousses d'", "gousses"),
    ("gousse d'", "gousse"),
    ("gousses de ", "gousses"),
    ("gousse de ", "gousse"),
    ("branches de ", "branches"),
    ("branche de ", "branche"),
    ("feuilles de ", "feuilles"),
    ("feuille de ", "feuille"),
    ("cubes de ", "cubes"),
    ("cube de ", "cube"),
    ("steaks de ", "steaks"),
    ("steak de ", "steak"),
    ("escalopes de ", "escalopes"),
    ("escalope de ", "escalope"),
    ("cuisses de ", "cuisses"),
    ("cuisse de ", "cuisse"),
]

UNIT_SYNONYMS: dict[str, str] = {
    "c. a s.": "c. à soupe",
    "c. a s": "c. à soupe",
    "c. à s.": "c. à soupe",
    "c. à s": "c. à soupe",
    "cas": "c. à soupe",
    "c à s": "c. à soupe",
    "cuillère à soupe": "c. à soupe",
    "cuillere a soupe": "c. à soupe",
    "cuillères à soupe": "c. à soupe",
    "cuilleres a soupe": "c. à soupe",
    "c. a c.": "c. à café",
    "c. a c": "c. à café",
    "c. à c.": "c. à café",
    "c. à c": "c. à café",
    "cac": "c. à café",
    "c à c": "c. à café",
    "cuillère à café": "c. à café",
    "cuillere a cafe": "c. à café",
    "cuillères à café": "c. à café",
    "cuilleres a cafe": "c. à café",
    "pincee": "pincée",
    "pincees": "pincée",
    "pincée": "pincée",
    "pincées": "pincée",
    "pièce": "item",
    "piece": "item",
    "pièces": "item",
    "pieces": "item",
    "item": "item",
    "items": "item",
    "": "item",
}

UNIT_AS_CUT: dict[str, str] = {
    "pave": "pavé",
    "paves": "pavés",
    "pavé": "pavé",
    "pavés": "pavés",
    "morceau": "morceau",
    "morceaux": "morceaux",
    "tranche": "tranche",
    "tranches": "tranches",
    "filet": "filet",
    "filets": "filets",
    "cube": "cube",
    "cubes": "cube",
    "gousse": "gousse",
    "gousses": "gousse",
    "branche": "branche",
    "branches": "branche",
    "feuille": "feuille",
    "feuilles": "feuille",
    "escalope": "escalope",
    "escalopes": "escalopes",
    "steak": "steak",
    "steaks": "steak",
    "blanc": "blanc",
    "blancs": "blanc",
    "cuisse": "cuisse",
    "cuisses": "cuisse",
}


MEASURABLE_PROTEIN_KEYWORDS = {
    "saumon",
    "poisson",
    "thon",
    "cabillaud",
    "colin",
    "lieu",
    "bar",
    "dorade",
    "truite",
    "maquereau",
    "sardine",
    "sole",
    "merlu",
    "églefin",
    "eglefin",
    "poulet",
    "boeuf",
    "porc",
    "dinde",
    "veau",
    "canard",
    "agneau",
    "viande",
    "bavette",
    "steak",
    "jambon",
    "lardons",
    "crevette",
    "crevettes",
    "gambas",
}

MASS_CUT_UNITS = {
    "pave",
    "paves",
    "pavé",
    "pavés",
    "filet",
    "filets",
    "steak",
    "steaks",
    "escalope",
    "escalopes",
    "blanc",
    "blancs",
    "cuisse",
    "cuisses",
    "morceau",
    "morceaux",
    "tranche",
    "tranches",
}


def strip_accents(s: str) -> str:
    """Remove diacritics from a string."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def canonical_ingredient(
    raw_name: str,
    raw_unit: str | None = None,
    raw_note: str | None = None,
) -> tuple[str, str, str | None]:
    """Extract canonical singular ingredient name, standard unit, and cut note.

    Examples:
        - "Saumon (pavés)", "pavés", "150 g chacun" -> ("Saumon", "g", "150 g chacun, pavés")
        - "Pave de saumon", "g", None -> ("Saumon", "g", "pavé")
        - "Huile d'olive", "c. a s.", None -> ("Huile d'olive", "c. à soupe", None)
        - "Avocat", "", None -> ("Avocat", "item", None)
    """
    name = (raw_name or "").strip()
    unit = (raw_unit or "").strip()
    note = (raw_note or "").strip() or None

    extracted_notes: list[str] = []
    if note:
        extracted_notes.append(note)

    # 1. Extract and strip text in parentheses
    paren_match = re.search(r"\s*\(([^)]+)\)", name)
    if paren_match:
        paren_content = paren_match.group(1).strip()
        if paren_content and paren_content.lower() not in " ".join(extracted_notes).lower():
            extracted_notes.append(paren_content)
        name = re.sub(r"\s*\([^)]+\)", "", name).strip()

    # 2. Extract cut prefix in name
    norm_name = strip_accents(name.lower())
    for prefix, cut_label in CUT_PREFIXES:
        norm_prefix = strip_accents(prefix)
        if norm_name.startswith(norm_prefix):
            name = name[len(prefix):].strip()
            if cut_label not in " ".join(extracted_notes).lower():
                extracted_notes.append(cut_label)
            break

    # 3. Check if unit was actually a cut name
    unit_lower = strip_accents(unit.lower())
    was_cut_unit = False
    if unit_lower in UNIT_AS_CUT:
        cut_label = UNIT_AS_CUT[unit_lower]
        if cut_label not in " ".join(extracted_notes).lower():
            extracted_notes.append(cut_label)
        was_cut_unit = True
        unit = ""

    # Physical measurability check:
    # Measurable proteins must be measured in metric units (grams), with cuts kept in notes.
    norm_name_after = strip_accents(name.lower())
    is_measurable_protein = any(
        kw in norm_name_after for kw in MEASURABLE_PROTEIN_KEYWORDS
    )
    if is_measurable_protein and (was_cut_unit or unit_lower in ("item", "piece", "pieces", "")):
        unit = "g"
    elif was_cut_unit:
        if unit_lower in MASS_CUT_UNITS:
            unit = "g"
        else:
            unit = "item"

    # 4. Normalize unit
    unit_norm = UNIT_SYNONYMS.get(unit.lower(), unit if unit else "item")

    # 5. Clean name capitalization
    if name:
        name = name[0].upper() + name[1:]

    final_note = ", ".join(extracted_notes) if extracted_notes else None
    return name, unit_norm, final_note


def normalize_name(value: str | None) -> str:
    """Normalize ingredient name for matching (strips accents, cut prefixes, parentheses, plurals)."""
    if not value:
        return ""
    s = value.strip().lower()
    # Remove text in parentheses
    s = re.sub(r"\s*\([^)]*\)", "", s)
    # Remove accents
    s = strip_accents(s)
    # Remove leading cut prefixes
    for prefix, _ in CUT_PREFIXES:
        norm_prefix = strip_accents(prefix)
        if s.startswith(norm_prefix):
            s = s[len(prefix):].strip()
            break
    # Replace non-alphanumeric with space
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()

    # Stem plurals (strip trailing 's' or 'x' for French plurals if word > 3 chars)
    words = []
    for w in s.split():
        if len(w) > 3 and w.endswith(("s", "x")) and not w.endswith(_STEM_EXCLUDE_SUFFIXES):
            w = w[:-1]
        words.append(w)
    return " ".join(words)


def unit_meta(unit: str | None) -> tuple[str, float]:
    """Return (base_unit, factor) for a unit, or (unit, 1.0) when unknown."""
    raw = unit.strip().lower() if unit else "item"
    normalized_unit = UNIT_SYNONYMS.get(raw, raw)
    base = _UNIT_BASE.get(normalized_unit)
    if not base:
        return normalized_unit, 1.0
    base_unit, factor = base
    return base_unit, factor


def to_base(quantity: float, unit: str | None) -> tuple[float, str]:
    """Convert a quantity into its base unit so different units compare equal.

    Unknown units pass through untouched: ``(quantity, normalized_unit)``.
    """
    raw = unit.strip().lower() if unit else "item"
    normalized_unit = UNIT_SYNONYMS.get(raw, raw)
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

