"""Canonical reference data seeder for Merise models in AdamHUB."""
from __future__ import annotations

import logging
from sqlmodel import Session, select

from app.models import (
    DietaryPreference,
    Ingredient,
    Tag,
    UnitOfMeasure,
    Utensil,
)

logger = logging.getLogger(__name__)

INITIAL_UNITS: list[dict] = [
    # Mass (base: g)
    {"code": "g", "label": "Gramme", "magnitude_type": "mass", "conversion_factor_to_base": 1.0},
    {"code": "kg", "label": "Kilogramme", "magnitude_type": "mass", "conversion_factor_to_base": 1000.0},
    {"code": "mg", "label": "Milligramme", "magnitude_type": "mass", "conversion_factor_to_base": 0.001},
    # Volume (base: ml)
    {"code": "ml", "label": "Millilitre", "magnitude_type": "volume", "conversion_factor_to_base": 1.0},
    {"code": "cl", "label": "Centilitre", "magnitude_type": "volume", "conversion_factor_to_base": 10.0},
    {"code": "dl", "label": "Décilitre", "magnitude_type": "volume", "conversion_factor_to_base": 100.0},
    {"code": "l", "label": "Litre", "magnitude_type": "volume", "conversion_factor_to_base": 1000.0},
    # Units / Counts (base: piece)
    {"code": "piece", "label": "Pièce", "magnitude_type": "unit", "conversion_factor_to_base": 1.0},
    {"code": "cac", "label": "Cuillère à café", "magnitude_type": "volume", "conversion_factor_to_base": 5.0},
    {"code": "cas", "label": "Cuillère à soupe", "magnitude_type": "volume", "conversion_factor_to_base": 15.0},
    {"code": "pincee", "label": "Pincée", "magnitude_type": "mass", "conversion_factor_to_base": 0.5},
    {"code": "gousse", "label": "Gousse", "magnitude_type": "unit", "conversion_factor_to_base": 1.0},
    {"code": "tranche", "label": "Tranche", "magnitude_type": "unit", "conversion_factor_to_base": 1.0},
    {"code": "botte", "label": "Botte", "magnitude_type": "unit", "conversion_factor_to_base": 1.0},
    {"code": "boite", "label": "Boîte", "magnitude_type": "unit", "conversion_factor_to_base": 1.0},
    {"code": "sachet", "label": "Sachet", "magnitude_type": "unit", "conversion_factor_to_base": 1.0},
]

INITIAL_DIETARY_PREFERENCES: list[dict] = [
    {
        "name": "Végétarien",
        "description": "Exclut la viande, la volaille et les poissons ou fruits de mer.",
    },
    {
        "name": "Végan",
        "description": "Exclut tout produit d'origine animale (viande, poisson, produits laitiers, œufs, miel).",
    },
    {
        "name": "Sans gluten",
        "description": "Convient aux personnes intolérantes ou cœliaques (sans blé, seigle, orge).",
    },
    {
        "name": "Sans lactose",
        "description": "Exclut les produits laitiers contenant du lactose.",
    },
    {
        "name": "Pescétarien",
        "description": "Exclut la viande et la volaille mais inclut poissons et fruits de mer.",
    },
    {
        "name": "Halal",
        "description": "Conforme aux prescriptions de l'alimentation islamique.",
    },
    {
        "name": "Casher",
        "description": "Conforme aux lois alimentaires juives (cacherout).",
    },
    {
        "name": "Cétogène (Keto)",
        "description": "Régime très pauvre en glucides et riche en lipides de qualité.",
    },
    {
        "name": "Faible en glucides (Low carb)",
        "description": "Apport limité en glucides et sucres raffinés.",
    },
]

INITIAL_UTENSILS: list[str] = [
    "Poêle",
    "Casserole",
    "Faitout / Marmite",
    "Four",
    "Four à micro-ondes",
    "Mixeur plongeant",
    "Blender",
    "Fouet",
    "Spatule",
    "Plat à gratin",
    "Saladier",
    "Couteau de chef",
    "Économe / Éplucheur",
    "Passoire",
    "Presse-ail",
    "Râpe à fromage",
    "Balance de cuisine",
    "Verre doseur",
    "Plaque de cuisson",
]

INITIAL_TAGS: list[str] = [
    "Rapide (< 20 min)",
    "Moins de 30 min",
    "Facile",
    "Batch cooking",
    "Sans cuisson",
    "Économique",
    "Familial",
    "Comfort food",
    "Healthy / Équilibré",
    "Saison : Printemps",
    "Saison : Été",
    "Saison : Automne",
    "Saison : Hiver",
]

INITIAL_INGREDIENTS: list[dict] = [
    # Épicerie salée
    {"name": "Farine de blé T55", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Riz basmati", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Pâtes Penne", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Pâtes Spaghetti", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Sel fin", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Poivre noir moulu", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Huile d'olive extra vierge", "category": "Épicerie salée", "default_unit_code": "ml"},
    {"name": "Huile de tournesol", "category": "Épicerie salée", "default_unit_code": "ml"},
    {"name": "Vinaigre balsamique", "category": "Épicerie salée", "default_unit_code": "ml"},
    {"name": "Sauce soja", "category": "Épicerie salée", "default_unit_code": "ml"},
    {"name": "Moutarde de Dijon", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Concentré de tomates", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Coulis de tomates", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Pois chiches en boîte", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Haricots rouges en boîte", "category": "Épicerie salée", "default_unit_code": "g"},
    {"name": "Bouillon de légumes", "category": "Épicerie salée", "default_unit_code": "ml"},
    {"name": "Bouillon de volaille", "category": "Épicerie salée", "default_unit_code": "ml"},
    # Épicerie sucrée
    {"name": "Sucre en poudre", "category": "Épicerie sucrée", "default_unit_code": "g"},
    {"name": "Sucre roux / Cassonade", "category": "Épicerie sucrée", "default_unit_code": "g"},
    {"name": "Chocolat noir pâtissier", "category": "Épicerie sucrée", "default_unit_code": "g"},
    {"name": "Miel", "category": "Épicerie sucrée", "default_unit_code": "g"},
    {"name": "Levure chimique", "category": "Épicerie sucrée", "default_unit_code": "sachet"},
    {"name": "Extrait de vanille", "category": "Épicerie sucrée", "default_unit_code": "cac"},
    # Fruits et Légumes
    {"name": "Oignon jaune", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Oignon rouge", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Ail", "category": "Fruits et Légumes", "default_unit_code": "gousse"},
    {"name": "Échalote", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Pomme de terre", "category": "Fruits et Légumes", "default_unit_code": "g"},
    {"name": "Carotte", "category": "Fruits et Légumes", "default_unit_code": "g"},
    {"name": "Tomate", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Courgette", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Poivron rouge", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Champignon de Paris", "category": "Fruits et Légumes", "default_unit_code": "g"},
    {"name": "Citron jaune", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Avocat", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Pomme Gala", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Banane", "category": "Fruits et Légumes", "default_unit_code": "piece"},
    {"name": "Épinards frais", "category": "Fruits et Légumes", "default_unit_code": "g"},
    {"name": "Persil plat", "category": "Fruits et Légumes", "default_unit_code": "botte"},
    {"name": "Coriandre fraîche", "category": "Fruits et Légumes", "default_unit_code": "botte"},
    {"name": "Basilic frais", "category": "Fruits et Légumes", "default_unit_code": "botte"},
    # Produits Frais & Crèmerie
    {"name": "Beurre doux", "category": "Produits Frais", "default_unit_code": "g"},
    {"name": "Beurre demi-sel", "category": "Produits Frais", "default_unit_code": "g"},
    {"name": "Lait demi-écrémé", "category": "Produits Frais", "default_unit_code": "ml"},
    {"name": "Crème fraîche épaisse", "category": "Produits Frais", "default_unit_code": "g"},
    {"name": "Crème liquide entière", "category": "Produits Frais", "default_unit_code": "ml"},
    {"name": "Œuf", "category": "Produits Frais", "default_unit_code": "piece"},
    {"name": "Parmesan râpé", "category": "Produits Frais", "default_unit_code": "g"},
    {"name": "Mozzarella", "category": "Produits Frais", "default_unit_code": "g"},
    {"name": "Emmental râpé", "category": "Produits Frais", "default_unit_code": "g"},
    {"name": "Fromage de chèvre frais", "category": "Produits Frais", "default_unit_code": "g"},
    {"name": "Yaourt nature", "category": "Produits Frais", "default_unit_code": "piece"},
    # Boucherie & Poissonnerie
    {"name": "Blanc de poulet", "category": "Boucherie & Poissonnerie", "default_unit_code": "g"},
    {"name": "Steak haché de bœuf 15%", "category": "Boucherie & Poissonnerie", "default_unit_code": "piece"},
    {"name": "Lardons fumés", "category": "Boucherie & Poissonnerie", "default_unit_code": "g"},
    {"name": "Pavé de saumon", "category": "Boucherie & Poissonnerie", "default_unit_code": "piece"},
    {"name": "Thon au naturel en boîte", "category": "Boucherie & Poissonnerie", "default_unit_code": "g"},
    {"name": "Crevettes décortiquées", "category": "Boucherie & Poissonnerie", "default_unit_code": "g"},
]


def seed_canonical_data(session: Session) -> dict[str, int]:
    """Seed initial canonical units, dietary preferences, utensils, tags, and ingredients.

    Idempotent: skips any record that already exists.
    """
    counts = {
        "units": 0,
        "dietary_preferences": 0,
        "utensils": 0,
        "tags": 0,
        "ingredients": 0,
    }

    # 1. Unités de mesure
    for u_data in INITIAL_UNITS:
        existing = session.get(UnitOfMeasure, u_data["code"])
        if not existing:
            unit = UnitOfMeasure(**u_data)
            session.add(unit)
            counts["units"] += 1
    session.commit()

    # 2. Régimes alimentaires
    for d_data in INITIAL_DIETARY_PREFERENCES:
        existing = session.exec(
            select(DietaryPreference).where(DietaryPreference.name == d_data["name"])
        ).first()
        if not existing:
            pref = DietaryPreference(**d_data)
            session.add(pref)
            counts["dietary_preferences"] += 1
    session.commit()

    # 3. Ustensiles
    for u_name in INITIAL_UTENSILS:
        existing = session.exec(
            select(Utensil).where(Utensil.name == u_name)
        ).first()
        if not existing:
            utensil = Utensil(name=u_name)
            session.add(utensil)
            counts["utensils"] += 1
    session.commit()

    # 4. Tags
    for t_label in INITIAL_TAGS:
        existing = session.exec(
            select(Tag).where(Tag.label == t_label)
        ).first()
        if not existing:
            tag = Tag(label=t_label)
            session.add(tag)
            counts["tags"] += 1
    session.commit()

    # 5. Ingrédients
    for i_data in INITIAL_INGREDIENTS:
        existing = session.exec(
            select(Ingredient).where(Ingredient.name == i_data["name"])
        ).first()
        if not existing:
            ing = Ingredient(**i_data)
            session.add(ing)
            counts["ingredients"] += 1
    session.commit()

    logger.info("Canonical seed completed: %s", counts)
    return counts
