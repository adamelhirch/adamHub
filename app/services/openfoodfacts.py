import re
from datetime import UTC, datetime, timedelta
import httpx
from sqlmodel import Session, select

from app.models.entities import OpenFoodFactsCache
from app.schemas.pantry import OpenFoodFactsProductDraft

OPENFOODFACTS_USER_AGENT = (
    "AdamHUB/1.0 (https://github.com/adamelhirch/adamHub; contact@adamelhirch.com)"
)
OPENFOODFACTS_API_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
CACHE_TTL_DAYS = 30

# Marketing and supermarket distributor prefixes/terms to strip from product titles
DISTRIBUTOR_BRANDS = [
    "carrefour extra",
    "carrefour classic",
    "carrefour bio",
    "carrefour sensation",
    "carrefour selection",
    "carrefour",
    "intermarché",
    "monique ranou",
    "chabrior",
    "paquito",
    "pâturages",
    "saint eloi",
    "simpl",
    "e.leclerc",
    "repère",
    "marche u",
    "u bio",
    "monoprix gourmet",
    "monoprix bio",
    "monoprix",
    "auchan",
    "casino",
    "leader price",
]

MARKETING_TERMS = [
    r"\bqualité supérieure\b",
    r"\bformat familial\b",
    r"\brecette traditionnelle\b",
    r"\bsans colorant\b",
    r"\bsans conservateur\b",
    r"\bsans arôme artificiel\b",
    r"\bpur porc\b",
    r"\bpur boeuf\b",
    r"\bextra\b",
    r"\bclassic\b",
    r"\bsélection\b",
    r"\bselection\b",
    r"\bbio\b",
    r"\bformat éco\b",
    r"\bformat promo\b",
    r"\blot de \d+\b",
    r"\bpack de \d+\b",
]

CATEGORY_KEYWORDS: list[tuple[list[str], str]] = [
    (["poisson", "saumon", "thon", "cabillaud", "colin", "truite", "crevette", "fruits de mer", "sardine", "maquereau"], "Poisson"),
    (["viande", "poulet", "dinde", "boeuf", "bœuf", "porc", "veau", "jambon", "lardons", "bacon", "steak"], "Viande"),
    (["lait", "fromage", "yaourt", "beurre", "crème", "creme", "emmental", "mozzarella", "parmesan", "chèvre", "comté"], "Produits_laitiers"),
    (["surgelé", "surgeles", "glace", "glaces", "sorbet"], "Surgelés"),
    (["boisson", "jus", "soda", "eau", "café", "the", "thé", "bière", "vin", "sirop"], "Boissons"),
    (["fruit", "pomme", "banane", "orange", "citron", "fraise", "avocat", "raisin", "poire"], "Fruits"),
    (["légume", "legume", "tomate", "carotte", "courgette", "oignon", "echalote", "échalote", "ail", "salade", "pomme de terre", "poireau", "champignon"], "Légumes"),
    (["pâte", "pate", "riz", "farine", "sucre", "huile", "vinaigre", "sel", "poivre", "conserve", "sauce", "épice", "epice", "biscuit", "chocolat", "céréale", "cereale", "lentille", "pois"], "Épicerie"),
]


def clean_openfoodfacts_product(raw_product: dict, barcode: str) -> OpenFoodFactsProductDraft:
    """Transforms raw Open Food Facts payload into a normalized, clean culinary draft.
    
    Strips brand marketing noise while preserving culinary varieties (e.g. 'Pâtes penne').
    """
    raw_name = (
        raw_product.get("product_name_fr")
        or raw_product.get("product_name")
        or raw_product.get("generic_name_fr")
        or raw_product.get("generic_name")
        or ""
    ).strip()

    brand = (
        raw_product.get("brands")
        or (raw_product.get("brands_tags", [None])[0] if raw_product.get("brands_tags") else None)
        or None
    )
    if brand:
        brand = brand.split(",")[0].strip()

    cleaned_name = raw_name

    # Strip brand name if present inside product title
    if brand:
        cleaned_name = re.sub(re.escape(brand), "", cleaned_name, flags=re.IGNORECASE)

    # Strip known distributor brand strings
    for dist in DISTRIBUTOR_BRANDS:
        cleaned_name = re.sub(r"\b" + re.escape(dist) + r"\b", "", cleaned_name, flags=re.IGNORECASE)

    # Strip marketing buzzwords
    for pattern in MARKETING_TERMS:
        cleaned_name = re.sub(pattern, "", cleaned_name, flags=re.IGNORECASE)

    # Clean leftover punctuation and multiple spaces
    cleaned_name = re.sub(r"[\(\)\[\]\-_,]+", " ", cleaned_name)
    cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip()

    # Extract quantity and unit
    quantity: float = 1.0
    unit: str = "item"
    missing_fields: list[str] = ["expires_at"]

    # Try explicit product_quantity field
    pq = raw_product.get("product_quantity")
    pq_unit = (raw_product.get("product_quantity_unit") or "").lower().strip()
    if pq is not None:
        try:
            val = float(pq)
            if val > 0:
                quantity = val
                if pq_unit in ("g", "kg", "ml", "cl", "l"):
                    unit = pq_unit
                elif pq_unit in ("gr", "grammes", "gramme"):
                    unit = "g"
                elif pq_unit in ("kilo", "kilogrammes", "kilogramme"):
                    unit = "kg"
                elif pq_unit in ("litre", "litres"):
                    unit = "l"
        except (ValueError, TypeError):
            pass

    # If unit is still item, try parsing from raw strings
    if unit == "item":
        qty_str = str(raw_product.get("quantity") or raw_name)
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|mg|l|cl|ml)\b", qty_str, flags=re.IGNORECASE)
        if match:
            try:
                num = float(match.group(1).replace(",", "."))
                raw_u = match.group(2).lower()
                if raw_u == "kg":
                    quantity = num * 1000.0 if num < 1 else num
                    unit = "g" if num < 1 else "kg"
                elif raw_u in ("g", "ml", "cl", "l"):
                    quantity = num
                    unit = raw_u
                elif raw_u == "mg":
                    quantity = num / 1000.0
                    unit = "g"
            except (ValueError, TypeError):
                pass

    # Remove quantity from cleaned title if still present (e.g. '500g')
    cleaned_name = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|mg|l|cl|ml)\b", "", cleaned_name, flags=re.IGNORECASE)
    cleaned_name = re.sub(r"\s+", " ", cleaned_name).strip()

    # Normalize culinary naming prefix if generic pasta/rice/etc.
    lower_cleaned = cleaned_name.lower()
    if "penne" in lower_cleaned and "pâte" not in lower_cleaned and "pate" not in lower_cleaned:
        cleaned_name = f"Pâtes {cleaned_name}"
    elif "spaghetti" in lower_cleaned and "pâte" not in lower_cleaned and "pate" not in lower_cleaned:
        cleaned_name = f"Pâtes {cleaned_name}"
    elif "coquillette" in lower_cleaned and "pâte" not in lower_cleaned and "pate" not in lower_cleaned:
        cleaned_name = f"Pâtes {cleaned_name}"
    elif "trombonne" in lower_cleaned and "pâte" not in lower_cleaned and "pate" not in lower_cleaned:
        cleaned_name = f"Pâtes {cleaned_name}"
    elif "tagliatelle" in lower_cleaned and "pâte" not in lower_cleaned and "pate" not in lower_cleaned:
        cleaned_name = f"Pâtes {cleaned_name}"
    elif "fusilli" in lower_cleaned and "pâte" not in lower_cleaned and "pate" not in lower_cleaned:
        cleaned_name = f"Pâtes {cleaned_name}"
    elif "basmati" in lower_cleaned and "riz" not in lower_cleaned:
        cleaned_name = f"Riz {cleaned_name}"

    if cleaned_name:
        # Capitalize nicely
        cleaned_name = cleaned_name[0].upper() + cleaned_name[1:]
    else:
        cleaned_name = raw_name or "Article sans nom"
        missing_fields.append("name")

    # Detect category
    category: str | None = None
    search_text = f"{raw_name} {' '.join(raw_product.get('categories_tags', []))}".lower()
    for keywords, cat in CATEGORY_KEYWORDS:
        if any(kw in search_text for kw in keywords):
            category = cat
            break
    if not category:
        category = "Épicerie"

    # Default storage location
    location = "Placard"
    if category in ("Poisson", "Viande", "Produits_laitiers"):
        location = "Réfrigérateur"
    elif category == "Surgelés":
        location = "Congélateur"

    nutriscore = (raw_product.get("nutriscore_grade") or None)
    if nutriscore:
        nutriscore = str(nutriscore).lower()

    image_url = (
        raw_product.get("image_front_url")
        or raw_product.get("image_url")
        or None
    )

    packaging = raw_product.get("packaging") or None

    return OpenFoodFactsProductDraft(
        barcode=barcode,
        found=True,
        raw_name=raw_name,
        brand=brand,
        suggested_name=cleaned_name,
        quantity=quantity,
        unit=unit,
        category=category,
        image_url=image_url,
        nutriscore=nutriscore,
        packaging=packaging,
        location=location,
        missing_fields=missing_fields,
    )


async def lookup_openfoodfacts_barcode(barcode: str, session: Session | None = None) -> OpenFoodFactsProductDraft:
    """Queries Open Food Facts for a barcode, using local cache first, returning a normalized draft."""
    barcode = barcode.strip()
    now = datetime.now(UTC)

    # 1. Check local cache if database session provided
    if session:
        cached = session.exec(
            select(OpenFoodFactsCache).where(
                OpenFoodFactsCache.barcode == barcode,
                OpenFoodFactsCache.expires_at > now,
            )
        ).first()
        if cached and cached.raw_payload:
            return clean_openfoodfacts_product(cached.raw_payload, barcode)

    # 2. Query external Open Food Facts v2 API
    url = OPENFOODFACTS_API_URL.format(barcode=barcode)
    headers = {"User-Agent": OPENFOODFACTS_USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == 1 and "product" in data:
                    product = data["product"]

                    # Cache the result in DB
                    if session:
                        cache_entry = OpenFoodFactsCache(
                            barcode=barcode,
                            raw_payload=product,
                            product_name=product.get("product_name_fr") or product.get("product_name"),
                            brand=product.get("brands"),
                            quantity_text=product.get("quantity"),
                            image_url=product.get("image_front_url") or product.get("image_url"),
                            nutriscore=product.get("nutriscore_grade"),
                            expires_at=now + timedelta(days=CACHE_TTL_DAYS),
                        )
                        session.merge(cache_entry)
                        session.commit()

                    return clean_openfoodfacts_product(product, barcode)
    except Exception:
        # In case of network errors, continue to not found draft
        pass

    # Not found in Open Food Facts
    return OpenFoodFactsProductDraft(
        barcode=barcode,
        found=False,
        raw_name=None,
        brand=None,
        suggested_name="",
        quantity=1.0,
        unit="item",
        category=None,
        location="Placard",
        missing_fields=["name", "quantity", "unit", "category", "expires_at"],
    )
