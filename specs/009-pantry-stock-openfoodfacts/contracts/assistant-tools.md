# AI Assistant Tools & Guardrails Contract

**Feature**: `009-pantry-stock-openfoodfacts`  
**Date**: 2026-09-15  
**Status**: Completed  

---

## 1. New Assistant Action: `pantry.lookup_barcode`

Registered in `app/skill/actions.py` under the pantry domain.

### Action Specification
- **Action**: `pantry.lookup_barcode`
- **Description**: "Look up product details and cleaned culinary suggestions from Open Food Facts using an EAN/UPC barcode."
- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "barcode": {
      "type": "string",
      "description": "EAN-13, EAN-8, or UPC barcode of the product."
    }
  },
  "required": ["barcode"]
}
```

### Response Schema
```json
{
  "barcode": "3560070557451",
  "found": true,
  "raw_name": "Carrefour Extra Penne Rigate 500g",
  "brand": "Carrefour Extra",
  "suggested_name": "Pâtes penne",
  "quantity": 500.0,
  "unit": "g",
  "category": "Épicerie",
  "location": "Placard",
  "image_url": "https://...",
  "missing_fields": ["expires_at"]
}
```

---

## 2. Updated Action: `pantry.update_item`

Expanded to accept full stock modification fields.

### Input Schema
```json
{
  "type": "object",
  "properties": {
    "item_id": { "type": "integer", "description": "ID of the pantry item to update." },
    "name": { "type": "string", "description": "Updated culinary name (e.g. 'Saumon frais')." },
    "quantity": { "type": "number", "minimum": 0, "description": "Exact numeric stock quantity." },
    "unit": { "type": "string", "enum": ["g", "kg", "ml", "cl", "l", "c. à soupe", "c. à café", "pincée", "item"] },
    "category": { "type": "string" },
    "location": { "type": "string", "enum": ["Réfrigérateur", "Placard", "Congélateur"] },
    "expires_at": { "type": "string", "format": "date", "description": "Expiration date (YYYY-MM-DD)." },
    "note": { "type": "string", "description": "Piece count or preparation note (e.g. '2 pavés')." }
  },
  "required": ["item_id"]
}
```

---

## 3. Updated Assistant System Directives (`context_builder.py`)

The system prompt in `app/services/assistant/context_builder.py` is updated at Section 8:

```markdown
8. DÉNOMINATION CANONIQUE ET MESURABILITÉ PHYSIQUE (STRICT & OBLIGATOIRE) :
   - Pour éviter les doublons et incohérences dans le stock et les recettes, applique STRICTEMENT ces règles :
   - DISTINCTION CULINAIRE DANS `name` : Différencie explicitement les états culinaires incompatibles (ex: "Saumon frais", "Saumon fumé", "Thon en boîte", "Pâtes penne", "Riz basmati"). Ne JAMAIS utiliser un terme flou qui mélange deux produits différents.
   - RÈGLE DE MESURABILITÉ PHYSIQUE :
     * Tout ingrédient pesable ou mesurable (viandes, poissons, pâtes, riz, farine, fromage râpé, liquides) DOIT être exprimé en unités métriques standard (`g`, `kg`, `ml`, `cl`, `l`).
     * Pour les poissons et viandes découpés en portions (ex: pavés de saumon, filets de poulet), spécifie TOUJOURS la quantité en grammes (ex: `quantity: 250`, `unit: "g"`).
     * La mention de découpe ou du nombre de portions appartient STRICTEMENT au champ `note` (ex: `note: "2 pavés"` ou `note: "2 pavés de 125 g"`).
   - UNITÉ `item` STRICTEMENT RÉSERVÉE AUX PIÈCES ENTIÈRES NATURELLES :
     * `unit: "item"` est autorisé UNIQUEMENT pour les produits qui se comptent naturellement à la pièce (ex: "Avocat", "Pomme", "Oeuf", "Citron", "Oignon", "Echalote").
     * INTERDICTION ABSOLUE d'utiliser les coupes comme unité : "pavés", "morceaux", "tranches", "gousses" sont PROSCRITS comme unité.
   - 1 INGRÉDIENT PAR LIGNE : Ne JAMAIS combiner deux ingrédients (créer "Sel" et "Poivre" séparément).
```
