from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Sequence

from sqlmodel import Session, col, or_, select

from app.models import (
    GroceryItem,
    GroceryToCartJob,
    MatchedCartItem,
    SubstituteProposal,
    SupermarketMapping,
    SupermarketSearchCache,
    SupermarketStore,
    SupermarketTargetType,
)

CULINARY_PORTION_UNITS = {
    "filet", "trait", "pincee", "pincée", "poignee", "poignée",
    "brin", "gousse", "feuille", "cuillere", "cuillère", "c. a soupe",
    "c. à soupe", "c. a cafe", "c. à café", "cas", "cac", "càs", "càc",
    "zeste", "noix", "larme", "goutte"
}

WEIGHT_FACTORS = {
    "kg": 1000.0, "kilo": 1000.0, "kilos": 1000.0,
    "g": 1.0, "gr": 1.0, "gramme": 1.0, "grammes": 1.0,
    "mg": 0.001
}

VOLUME_FACTORS = {
    "l": 1000.0, "litre": 1000.0, "litres": 1000.0,
    "cl": 10.0, "centilitre": 10.0, "centilitres": 10.0,
    "dl": 100.0,
    "ml": 1.0, "millilitre": 1.0, "millilitres": 1.0
}


CULINARY_STOP_WORDS = {
    # French prepositions, conjunctions, articles, pronouns
    "de", "du", "des", "le", "la", "les", "un", "une", "d", "l",
    "en", "au", "aux", "avec", "sans", "sur", "sous", "ou", "et", "pour", "par",
    # Culinary states, cuts, packaging, and descriptions
    "frais", "fraiche", "fraîche", "fraiches", "fraîches",
    "entier", "entiere", "entière", "entiers", "entières",
    "liquide", "liquides", "epais", "epaisse", "épais", "épaisse",
    "sec", "seche", "sèche", "seches", "sèches", "seche", "séché", "séchée", "séchés", "séchées",
    "doux", "douce", "demi", "ecreme", "écrémé", "ecremee", "écrémée",
    "hache", "haché", "hachee", "hachée", "rape", "râpé", "rapee", "râpée",
    "emince", "émincé", "emincee", "émincée", "coupe", "coupé", "coupee", "coupée",
    "cuit", "cuite", "cuits", "cuites", "cru", "crue",
    "nature", "naturel", "naturelle", "standard",
    "morceau", "morceaux", "cube", "cubes", "tranche", "tranches",
    "filet", "filets", "pave", "pavé", "paves", "pavés",
    "bio", "biologique", "biologiques",
    # Container, packaging and cut words to strip when identifying primary ingredient noun
    "gousse", "gousses", "tete", "tête", "tetes", "têtes",
    "pot", "pots", "brique", "briques", "boite", "boîte", "boites", "boîtes",
    "sachet", "sachets", "flacon", "flacons", "paquet", "paquets",
    "bouteille", "bouteilles", "barquette", "barquettes", "tube", "tubes",
    "lot", "lots", "pack", "packs",
}

from app.services.supermarket.culinary_guardrails import (
    INCOMPATIBLE_HEAD_NOUNS_MAP,
    is_budget_first_price,
    is_disqualified_by_culinary_guardrails,
)

INCOMPATIBLE_HEAD_NOUNS = INCOMPATIBLE_HEAD_NOUNS_MAP


def token_matches_keyword(keyword: str, token: str) -> bool:
    """Check if token matches culinary keyword with French singular/plural inflection and ligatures."""
    k = keyword.lower().replace("œ", "oe").replace("æ", "ae")
    t = token.lower().replace("œ", "oe").replace("æ", "ae")
    if k == t:
        return True
    if t == k + "s" or t == k + "x":
        return True
    if k == t + "s" or k == t + "x":
        return True
    return False


def extract_ingredient_keywords(raw_name: str) -> tuple[str, list[str]]:
    """Extract primary head noun and core keywords from an ingredient string.

    Example: 'riz arborio (ou carnaroli)' -> ('riz', ['riz', 'arborio'])
             'crème liquide entière' -> ('crème', ['crème'])
             'saumon frais sans peau' -> ('saumon', ['saumon', 'peau'])
    """
    clean = re.sub(r"\(.*?\)", "", raw_name).strip().lower()
    clean = clean.replace("œ", "oe").replace("æ", "ae")
    tokens = [w for w in re.split(r"[^\wÀ-ÿ]+", clean) if len(w) >= 2]
    core = [w for w in tokens if w not in CULINARY_STOP_WORDS]
    if core:
        head_noun = core[0]
    elif tokens:
        head_noun = tokens[0]
        core = [head_noun]
    else:
        head_noun = clean.strip()
        core = [head_noun] if head_noun else []
    return head_noun, core


def parse_product_metrics(packaging: str | None, name: str | None = "") -> tuple[float | None, float | None, int]:
    p = packaging or ""
    n = name or ""
    text = f"{p} {n}".lower().replace(",", ".")

    trailing_weight = re.search(r"-\s*(\d+(?:\.\d+)?)\s*(kg|g|gr)\b", text)
    trailing_vol = re.search(r"-\s*(\d+(?:\.\d+)?)\s*(l|cl|ml)\b", text)

    weight_g = None
    if trailing_weight:
        val = float(trailing_weight.group(1))
        weight_g = val * 1000.0 if trailing_weight.group(2) == "kg" else val
    else:
        kg_m = re.search(r"(\d+(?:\.\d+)?)\s*kg\b", text)
        g_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:g|gr)\b", text)
        if kg_m:
            weight_g = float(kg_m.group(1)) * 1000.0
        elif g_m:
            weight_g = float(g_m.group(1))

    volume_ml = None
    if trailing_vol:
        val = float(trailing_vol.group(1))
        unit = trailing_vol.group(2)
        volume_ml = val * 1000.0 if unit == "l" else (val * 10.0 if unit == "cl" else val)
    else:
        l_m = re.search(r"(\d+(?:\.\d+)?)\s*l\b", text)
        cl_m = re.search(r"(\d+(?:\.\d+)?)\s*cl\b", text)
        ml_m = re.search(r"(\d+(?:\.\d+)?)\s*ml\b", text)
        if l_m:
            volume_ml = float(l_m.group(1)) * 1000.0
        elif cl_m:
            volume_ml = float(cl_m.group(1)) * 10.0
        elif ml_m:
            volume_ml = float(ml_m.group(1))

    count_m = re.search(r"(?:bo[îi]te\s+de|pack\s+de|lot\s+de|x\s*|les\s+)\s*(\d+)", text, re.IGNORECASE)
    count = int(count_m.group(1)) if count_m else 1

    return weight_g, volume_ml, count


def calculate_commercial_quantity(
    raw_quantity: float | None,
    unit: str | None,
    packaging: str | None,
    product_name: str | None,
) -> float:
    """Convert requested grocery item quantity/unit to commercial retail units sold by drive."""
    raw_qty = float(raw_quantity) if raw_quantity and raw_quantity > 0 else 1.0
    u = (unit or "item").strip().lower()

    # 1. Culinary portion/seasoning units (e.g. 2 filets d'huile, 1 pincée de sel, 2 traits de citron)
    if any(c_unit in u for c_unit in CULINARY_PORTION_UNITS):
        return 1.0

    pack_weight_g, pack_vol_ml, pack_count = parse_product_metrics(packaging, product_name)

    # 2. Weight requested (g, kg, mg)
    for w_key, factor in WEIGHT_FACTORS.items():
        if u == w_key or u.startswith(w_key + " ") or u.startswith(w_key + ","):
            req_g = raw_qty * factor
            if pack_weight_g and pack_weight_g > 0:
                return float(max(1, math.ceil(req_g / pack_weight_g)))
            if req_g < 1000.0:
                return 1.0
            return float(max(1, math.ceil(req_g / 1000.0)))

    # 3. Volume requested (cl, ml, l, dl)
    for v_key, factor in VOLUME_FACTORS.items():
        if u == v_key or u.startswith(v_key + " ") or u.startswith(v_key + ","):
            req_ml = raw_qty * factor
            if pack_vol_ml and pack_vol_ml > 0:
                return float(max(1, math.ceil(req_ml / pack_vol_ml)))
            if req_ml < 1000.0:
                return 1.0
            return float(max(1, math.ceil(req_ml / 1000.0)))

    # 4. Count / discrete items (e.g. 6 oeufs, 2 briques)
    if pack_count and pack_count > 1:
        return float(max(1, math.ceil(raw_qty / pack_count)))

    return float(max(1, math.ceil(raw_qty)))

PRIVATE_LABELS_BY_STORE: dict[SupermarketStore, list[str]] = {
    SupermarketStore.LECLERC: [
        "marque repère",
        "nos régions ont du talent",
        "eco+",
        "bio village",
        "rustica",
        "traditions d'asie",
    ],
    SupermarketStore.AUCHAN: [
        "auchan",
        "pouce",
        "mmm!",
        "auchan bio",
    ],
    SupermarketStore.CARREFOUR: [
        "carrefour",
        "carrefour classic'",
        "carrefour bio",
        "simpl",
        "filière qualité carrefour",
    ],
    SupermarketStore.INTERMARCHE: [
        "monique ranou",
        "pâturages",
        "chabrior",
        "paquito",
        "top budget",
        "saint eloi",
        "odyssée",
        "itineraires des saveurs",
    ],
}


class CartMatcherService:
    """Resolves generic grocery items into real store SKUs according to optimization strategy."""

    @classmethod
    def match_grocery_item(
        cls,
        session: Session,
        item: GroceryItem,
        *,
        store: SupermarketStore,
        strategy: str = "mdd",
        user_id: int | None = None,
    ) -> MatchedCartItem | None:
        """Resolve a grocery item into a MatchedCartItem."""
        now = datetime.now(UTC)

        clean_name = item.name.strip().lower()
        # Extract core culinary keywords
        head_noun, core_words = extract_ingredient_keywords(clean_name)
        search_terms = core_words if core_words else [clean_name]

        # ── Step 1: Historical verified mapping (Priority 1) ─────────────────
        if user_id is not None:
            prev_matched_stmt = (
                select(MatchedCartItem)
                .join(GroceryToCartJob, MatchedCartItem.job_id == GroceryToCartJob.id)
                .where(
                    GroceryToCartJob.user_id == user_id,
                    GroceryToCartJob.store == store,
                    GroceryToCartJob.status.in_(["completed", "synced"]),
                    MatchedCartItem.status != "removed",
                    MatchedCartItem.cache_id.isnot(None),
                )
                .order_by(col(MatchedCartItem.id).desc())
            )
            prev_matches = session.exec(prev_matched_stmt).all()
            for prev_matched in prev_matches:
                p_name = (prev_matched.name or "").lower()
                p_tokens = set(re.split(r"[^\wÀ-ÿ]+", p_name))
                p_head_noun, _ = extract_ingredient_keywords(p_name)

                # Reject incompatible head nouns
                if head_noun in INCOMPATIBLE_HEAD_NOUNS:
                    if p_head_noun in INCOMPATIBLE_HEAD_NOUNS[head_noun]:
                        continue

                # Reject historical items violating culinary guardrails
                disq_hist, _ = is_disqualified_by_culinary_guardrails(
                    head_noun,
                    search_terms,
                    prev_matched.name or "",
                    prev_matched.brand,
                )
                if disq_hist:
                    continue

                # Check if head noun matches
                if not (token_matches_keyword(head_noun, p_head_noun) or any(token_matches_keyword(head_noun, t) for t in p_tokens)):
                    continue

                if prev_matched.cache_id:
                    cache_row = session.get(SupermarketSearchCache, prev_matched.cache_id)
                    if cache_row:
                        unit_price = int(round((cache_row.price_amount or 0) * 100))
                        qty = calculate_commercial_quantity(
                            item.quantity,
                            item.unit,
                            cache_row.packaging,
                            cache_row.name,
                        )
                        return MatchedCartItem(
                            grocery_item_id=item.id,
                            cache_id=cache_row.id,
                            external_id=cache_row.external_id,
                            name=cache_row.name,
                            brand=cache_row.brand,
                            packaging=cache_row.packaging,
                            image_url=cache_row.image_url,
                            product_url=cache_row.product_url,
                            quantity=qty,
                            unit_price_cents=unit_price,
                            total_price_cents=int(round(unit_price * qty)),
                            match_type="exact_history",
                            status="staged",
                        )

        # Query cache for store
        stmt = select(SupermarketSearchCache).where(
            SupermarketSearchCache.store == store,
        )
        conditions = [
            col(SupermarketSearchCache.query).ilike(f"%{clean_name}%"),
            col(SupermarketSearchCache.name).ilike(f"%{clean_name}%"),
        ]
        for w in search_terms[:3]:
            conditions.append(col(SupermarketSearchCache.name).ilike(f"%{w}%"))
            conditions.append(col(SupermarketSearchCache.query).ilike(f"%{w}%"))
        stmt = stmt.where(or_(*conditions))

        candidates = list(session.exec(stmt).all())
        is_fallback_store = False
        if not candidates:
            # Fallback: check other store caches so the user has authentic reference products
            stmt_fallback = select(SupermarketSearchCache)
            conditions_fallback = [
                col(SupermarketSearchCache.query).ilike(f"%{clean_name}%"),
                col(SupermarketSearchCache.name).ilike(f"%{clean_name}%"),
            ]
            for w in search_terms[:3]:
                conditions_fallback.append(col(SupermarketSearchCache.name).ilike(f"%{w}%"))
                conditions_fallback.append(col(SupermarketSearchCache.query).ilike(f"%{w}%"))
            stmt_fallback = stmt_fallback.where(or_(*conditions_fallback))
            candidates = list(session.exec(stmt_fallback).all())
            if candidates:
                is_fallback_store = True
            else:
                return None

        # Filter and score candidates: MUST match at least one core keyword and pass culinary guardrails
        mdd_brands = PRIVATE_LABELS_BY_STORE.get(store, [])

        scored_candidates: list[tuple[tuple, SupermarketSearchCache]] = []
        for cand in candidates:
            cand_name = (cand.name or "").lower().replace("œ", "oe").replace("æ", "ae")
            cand_brand = (cand.brand or "").lower().replace("œ", "oe").replace("æ", "ae")
            cand_tokens = set(re.split(r"[^\wÀ-ÿ]+", cand_name))
            cand_head_noun, _ = extract_ingredient_keywords(cand_name)
            price = cand.price_amount or 999.0

            # 1. Reject incompatible head nouns
            if head_noun in INCOMPATIBLE_HEAD_NOUNS:
                incompat = INCOMPATIBLE_HEAD_NOUNS[head_noun]
                if cand_head_noun in incompat or any(token_matches_keyword(bad, cand_head_noun) for bad in incompat):
                    continue

            # 2. Universal culinary guardrails (ready-to-eat dishes, cold cuts, salads, soups, essential qualifiers)
            disqualified, _ = is_disqualified_by_culinary_guardrails(
                head_noun,
                search_terms,
                cand.name,
                cand.brand,
            )
            if disqualified:
                continue

            # 3. Match core keywords using token inflection matching (prevents substring matching like 'ail' in 'volaille')
            matched_core = [w for w in search_terms if any(token_matches_keyword(w, t) for t in cand_tokens)]
            if not matched_core:
                continue

            # 4. Check head noun alignment
            cand_matches_head_noun = token_matches_keyword(head_noun, cand_head_noun)
            has_head_noun = cand_matches_head_noun or any(token_matches_keyword(head_noun, t) for t in cand_tokens)

            # 5. Compute match fidelity tier
            all_words = [w for w in re.split(r"[^\wÀ-ÿ]+", clean_name) if len(w) >= 2]
            matched_all_words = sum(1 for w in all_words if any(token_matches_keyword(w, t) for t in cand_tokens))

            if cand_matches_head_noun and len(matched_core) == len(search_terms):
                tier = 3  # High-fidelity exact match
            elif has_head_noun:
                tier = 2  # Compatible primary food item
            else:
                tier = 1  # Substitute / partial match

            keyword_score = matched_all_words * 50

            is_first_price = is_budget_first_price(cand.brand, cand.name)
            is_core_mdd = any(b in cand_brand or b in cand_name for b in mdd_brands) and not is_first_price
            is_bio = "bio" in cand_brand or "bio" in cand_name or "biologique" in cand_name

            if strategy in ["budget", "cheapest"]:
                # Priority 1: Match Tier
                # Priority 2: First-price hard discount bonus (200), then core MDD (100)
                # Priority 3: Lowest absolute price
                # Priority 4: Keyword accuracy
                first_price_bonus = 200 if is_first_price else (100 if is_core_mdd else 0)
                score_tuple = (tier, first_price_bonus, -price, keyword_score)
            elif strategy == "bio":
                bio_bonus = 200 if is_bio else 0
                mdd_bonus = 50 if (is_core_mdd or is_first_price) else 0
                score_tuple = (tier, bio_bonus, keyword_score, mdd_bonus, -price)
            else:
                # Default MDD strategy:
                # Core store brand (200) > First price (100) > National brands (0)
                # Keyword accuracy prioritizes requested descriptor (e.g. demi-écrémé) over generic lower price
                mdd_bonus = 200 if is_core_mdd else (100 if is_first_price else 0)
                score_tuple = (tier, mdd_bonus, keyword_score, -price)

            scored_candidates.append((score_tuple, cand))

        if not scored_candidates:
            return None

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best = scored_candidates[0][1]

        cand_name_lower = (best.name or "").lower()
        cand_brand_lower = (best.brand or "").lower()
        if is_fallback_store:
            match_type = "substitute"
        elif strategy == "budget":
            match_type = "budget"
        elif strategy == "bio" and ("bio" in cand_name_lower or "bio" in cand_brand_lower):
            match_type = "bio"
        elif any(b in cand_brand_lower or b in cand_name_lower for b in mdd_brands):
            match_type = "mdd"
        else:
            match_type = "mdd"

        qty = calculate_commercial_quantity(
            item.quantity,
            item.unit,
            best.packaging,
            best.name,
        )

        unit_price = int(round((best.price_amount or 0) * 100))

        return MatchedCartItem(
            grocery_item_id=item.id,
            cache_id=best.id,
            external_id=best.external_id,
            name=best.name,
            brand=best.brand,
            packaging=best.packaging,
            image_url=best.image_url,
            product_url=best.product_url,
            quantity=qty,
            unit_price_cents=unit_price,
            total_price_cents=int(round(unit_price * qty)),
            match_type=match_type,
            status="staged",
        )

    @classmethod
    def find_substitute_proposal(
        cls,
        session: Session,
        item: GroceryItem,
        matched: MatchedCartItem,
        *,
        store: SupermarketStore,
        strategy: str = "mdd",
    ) -> SubstituteProposal | None:
        clean_name = item.name.strip().lower()
        head_noun, core_words = extract_ingredient_keywords(clean_name)
        search_terms = core_words if core_words else [clean_name]

        stmt = select(SupermarketSearchCache).where(
            SupermarketSearchCache.id != matched.cache_id,
        )
        conditions = [
            col(SupermarketSearchCache.query).ilike(f"%{clean_name}%"),
            col(SupermarketSearchCache.name).ilike(f"%{clean_name}%"),
        ]
        for w in search_terms[:3]:
            conditions.append(col(SupermarketSearchCache.name).ilike(f"%{w}%"))
            conditions.append(col(SupermarketSearchCache.query).ilike(f"%{w}%"))
        stmt = stmt.where(or_(*conditions))

        alts = list(session.exec(stmt).all())
        valid_alts = []
        for a in alts:
            a_name = (a.name or "").lower()
            a_tokens = set(re.split(r"[^\wÀ-ÿ]+", a_name))
            a_head_noun, _ = extract_ingredient_keywords(a_name)

            if head_noun in INCOMPATIBLE_HEAD_NOUNS:
                incompat = INCOMPATIBLE_HEAD_NOUNS[head_noun]
                if a_head_noun in incompat or any(token_matches_keyword(bad, a_head_noun) for bad in incompat):
                    continue

            if head_noun in PROCESSED_DISH_DISQUALIFIERS:
                disq_words = PROCESSED_DISH_DISQUALIFIERS[head_noun]
                if any(any(token_matches_keyword(bad, t) for t in a_tokens) for bad in disq_words):
                    continue

            disqualified = False
            for qual_key, qual_synonyms in ESSENTIAL_QUALIFIERS.items():
                if any(token_matches_keyword(qual_key, w) for w in search_terms):
                    if not any(any(token_matches_keyword(syn, t) for t in a_tokens) for syn in qual_synonyms):
                        disqualified = True
                        break
            if disqualified:
                continue

            if any(any(token_matches_keyword(kw, t) for t in a_tokens) for kw in search_terms):
                valid_alts.append(a)

        if not valid_alts:
            return None

        alt = valid_alts[0]
        alt_price = int(round((alt.price_amount or 0) * 100))
        price_diff = alt_price - matched.unit_price_cents
        reason = "Alternative premier prix" if price_diff < 0 else "Format ou marque alternative disponible"

        return SubstituteProposal(
            matched_item_id=matched.id or 0,
            alternative_cache_id=alt.id or 0,
            alternative_name=alt.name,
            alternative_brand=alt.brand,
            alternative_unit_price_cents=alt_price,
            price_difference_cents=price_diff,
            reason=reason,
            status="pending",
        )

