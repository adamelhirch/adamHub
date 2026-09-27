from __future__ import annotations

import re
from typing import Sequence

# ── 1. Termes d'exclusion universels pour ingrédients culinaires bruts ──────────
# Tout ingrédient brut (viande, poisson, légume sec, féculent, légume frais)
# ne doit JAMAIS être satisfait par un plat cuisiné traiteur, un en-cas ou un substitut.
UNIVERSAL_READY_TO_EAT_DISQUALIFIERS = {
    # Plats préparés & traiteur micro-ondable
    "plat", "plats", "repas", "cuisiné", "cuisine", "cuisinés", "cuisines",
    "micro-ondable", "microondable", "barquette", "traiteur",
    "box", "bowl", "bowls",
    # Salades composées prêtes à consommer
    "salade", "salades",
    # Sandwichs, wraps & snacking
    "sandwich", "sandwichs", "wrap", "wraps", "panini", "croque", "croques",
    "snack", "snacks", "chips", "cracker", "crackers",
    # Pizzas, quiches & tourtes
    "pizza", "pizzas", "quiche", "quiches", "tourte", "tourtes", "tarte", "tartes",
    # Soupes & veloutés préparés liquides
    "velouté", "veloute", "veloutés", "veloutes", "potage", "potages",
    # Tartinables & apéritifs industriels
    "houmous", "hummus", "tapenade", "rillette", "rillettes", "terrine", "terrines",
    "pâté", "pate", "mousse", "tartinable", "tartinables", "dip", "dips",
    # Faux-semblants / substituts industriels ultra-transformés (quand on cherche du brut)
    "tranche", "tranches", "allumette", "allumettes", "boulette", "boulettes",
    "galette", "galettes",
}

# ── 2. Disqualificateurs spécifiques par famille d'ingrédients bruts ────────────
CATEGORY_SPECIFIC_DISQUALIFIERS: dict[str, set[str]] = {
    # Légumineuses (lentilles, pois chiches, haricots secs, fèves, pois cassés)
    "lentilles": {
        "tranche", "tranches", "salade", "salades", "houmous", "hummus",
        "velouté", "veloute", "veloutés", "veloutes", "soupe", "soupes",
        "boulette", "boulettes", "allumette", "allumettes", "repas", "plat", "plats",
        "végé", "vege", "vegetal", "végétal", "vegetale", "végétale", "substitut",
        "chips", "snack", "tartinable", "curry préparé", "dahl préparé",
    },
    "pois chiches": {
        "houmous", "hummus", "salade", "salades", "snack", "chips",
        "repas", "plat", "plats", "galette", "galettes", "falafel", "falafels",
    },
    "haricots": {
        "salade", "salades", "repas", "plat", "plats", "chili préparé",
        "burger", "galette",
    },

    # Volailles & Viandes (poulet, dinde, bœuf, porc)
    "poulet": {
        "nugget", "nuggets", "cordon", "cordons", "pané", "panés", "pane", "panes",
        "croquette", "croquettes", "sandwich", "sandwichs", "salade", "salades",
        "chips", "soupe", "velouté", "terrine", "pâté", "bouillon", "fond",
        "arôme", "arome", "croque", "pizza", "ballottine",
    },
    "dinde": {
        "cordon", "cordons", "pané", "panés", "nugget", "nuggets", "salade",
    },
    "viande": {
        "pizza", "sauce", "bolognaise", "ravioli", "raviolis", "lasagne", "lasagnes",
        "plat", "hachis", "terrine", "pâté", "saucisson", "chips",
    },
    "boeuf": {
        "pizza", "ravioli", "raviolis", "lasagne", "lasagnes", "terrine", "bouillon",
    },

    # Poissons & Fruits de mer
    "saumon": {
        "pizza", "quiche", "tarte", "lasagne", "lasagnes", "pâtes", "pates",
        "salade", "salades", "rillette", "rillettes", "terrine", "mousse",
        "croquette", "croquettes", "croque", "plat", "repas", "soupe",
    },
    "thon": {
        "salade", "salades", "sandwich", "sandwichs", "rillette", "rillettes",
        "pizza", "tarte", "quiche", "repas", "plat",
    },
    "cabillaud": {
        "pané", "panés", "croquette", "croquettes", "plat", "repas", "parmentier",
    },

    # Matières grasses & Produits laitiers
    "beurre": {
        "biscuit", "biscuits", "brioche", "croissant", "viennoiserie", "pâte",
        "sablé", "sablés", "madeleine", "madeleines", "gâteau", "gateau",
        "sauce", "sel", "escargot", "escargots",
    },
    "crème": {
        "glace", "glaces", "dessert", "desserts", "biscuit", "biscuits",
        "caramel", "liqueur", "chocolat",
    },
    "lait": {
        "chocolat", "boisson", "milkshake", "biscuit", "céréale", "cereales",
        "glace", "dessert", "crème dessert",
    },

    # Condiments, épices & assaisonnements
    "sel": {
        "beurre", "margarine", "fromage", "chips", "sauce", "biscuit", "biscuits",
        "plat", "poisson", "viande", "biscotte",
    },
    "poivre": {
        "saucisson", "pâté", "pate", "terrine", "viande", "fromage", "chips",
    },
    "ail": {
        "bouillon", "viande", "poulet", "volaille", "chips", "soupe", "velouté",
        "sauce", "pizza", "crouton", "croûtons", "biscotte", "pain",
    },
    "bouillon": {
        "chips", "sauce", "soupe",
    },

    # Féculents
    "riz": {
        "salade", "salades", "repas", "plat", "plats", "poêlée", "poelee",
        "dessert", "gâteau", "gateau", "galette", "galettes", "snack",
    },
    "pâtes": {
        "salade", "salades", "repas", "plat", "plats", "box", "poêlée", "poelee",
        "sauce", "chips",
    },

    # Légumes & Bases
    "tomates": {
        "sauce", "bolognaise", "ketchup", "jus", "chips", "pizza", "plat",
    },
    "oignon": {
        "chips", "soupe", "sauce", "biscuit",
    },
}

# ── 3. Qualificateurs essentiels (mots obligatoires pour éviter les faux-amis) ──
ESSENTIAL_QUALIFIERS_MAP: dict[str, list[str]] = {
    "coco": ["coco"],
    "concentré": ["concentré", "concentre"],
    "soja": ["soja"],
    "olive": ["olive"],
    "balsamique": ["balsamique"],
    "corail": ["corail"],
    "cidre": ["cidre"],
    "basmati": ["basmati"],
    "frais": ["frais", "fraiche", "fraîche"],
    "fumé": ["fumé", "fume", "fumée", "fumee"],
    "entier": ["entier", "entière", "entiere"],
    "doux": ["doux"],
}

# ── 4. Noms de têtes incompatibles (Faux-amis sémantiques complets) ──────────────
INCOMPATIBLE_HEAD_NOUNS_MAP: dict[str, set[str]] = {
    "sel": {"beurre", "margarine", "fromage", "chips", "sauce", "biscuit", "plat", "poisson", "viande"},
    "ail": {"bouillon", "viande", "poulet", "volaille", "chips", "soupe", "velouté", "sauce", "pizza"},
    "sucre": {"bonbon", "biscuit", "gateau", "gâteau", "chocolat", "soda"},
    "poivre": {"saucisson", "pâté", "terrine", "viande"},
    "beurre": {"sel", "sucre", "huile"},
    "lentilles": {"salade", "tranche", "tranches", "houmous", "velouté", "soupe", "boulette", "boulettes", "allumette", "allumettes", "repas"},
}

# ── 5. Marques Premier Prix (Budget / Éco) par magasin ──────────────────────────
BUDGET_FIRST_PRICE_BRANDS = {
    "simpl",          # Carrefour
    "eco+",           # E.Leclerc
    "pouce",          # Auchan
    "top budget",     # Intermarché
    "petit prix",
    "premier prix",
}

# ── 6. Fonctions de validation et de filtrage ──────────────────────────────────

def is_disqualified_by_culinary_guardrails(
    head_noun: str,
    search_terms: Sequence[str],
    candidate_name: str,
    candidate_brand: str | None = None,
) -> tuple[bool, str | None]:
    """Inspect candidate product against culinary sanity rules.

    Returns (is_disqualified, reason).
    """
    c_name = candidate_name.strip().lower()
    c_brand = (candidate_brand or "").strip().lower()
    full_text = f"{c_name} {c_brand}"
    cand_tokens = set(re.split(r"[^\wÀ-ÿ]+", full_text))

    # 1. Vérification contre les disqualificateurs spécifiques de la famille
    if head_noun in CATEGORY_SPECIFIC_DISQUALIFIERS:
        for bad_word in CATEGORY_SPECIFIC_DISQUALIFIERS[head_noun]:
            if bad_word in cand_tokens or any(t.startswith(bad_word) for t in cand_tokens):
                return True, f"Contient un terme interdit pour '{head_noun}': '{bad_word}'"

    # 2. Si c'est un aliment de base brut, vérifier les disqualificateurs universels prêt-à-manger
    # (à condition que la recherche elle-même ne demande pas ce plat expressément)
    is_staple = head_noun in CATEGORY_SPECIFIC_DISQUALIFIERS
    if is_staple:
        for disq in UNIVERSAL_READY_TO_EAT_DISQUALIFIERS:
            # Ne pas disqualifier si l'utilisateur a spécifiquement tapé ce mot
            if disq in search_terms:
                continue
            if disq in cand_tokens:
                return True, f"Produit transformé/prêt-à-consommer interdit pour un ingrédient brut: '{disq}'"

    # 3. Vérification des qualificateurs indispensables (ex: coco, corail, concentré)
    for qual_key, synonyms in ESSENTIAL_QUALIFIERS_MAP.items():
        # Si la recherche exigeait ce qualificateur
        if qual_key in search_terms or any(s in search_terms for s in synonyms):
            # Le candidat DOIT avoir au moins un des synonymes
            if not any(s in cand_tokens for s in synonyms):
                return True, f"Qualificateur essentiel manquant: '{qual_key}'"

    return False, None


def is_budget_first_price(brand: str | None, name: str | None) -> bool:
    """Return True if candidate belongs to a 1st price / hard discount tier."""
    b = (brand or "").lower()
    n = (name or "").lower()
    return any(p in b or p in n for p in BUDGET_FIRST_PRICE_BRANDS)
