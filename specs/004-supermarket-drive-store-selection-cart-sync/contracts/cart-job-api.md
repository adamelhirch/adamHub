# Contract: Supermarket Cart Job & Review API

**Base Path**: `/api/v1/supermarket/cart/jobs`
**Authentication**: Header `Authorization: Bearer <JWT>` ou `X-API-Key: <key>` (`CurrentOrOwnerUser`)

---

## 1. Création et Préparation du Panier Brouillon (Staging)

### `POST /api/v1/supermarket/cart/jobs`
Génère le staging local du panier à partir des articles non cochés de la liste de courses pour le magasin sélectionné.

#### Request Body
```json
{
  "store": "leclerc",
  "external_store_id": "0123",
  "optimization_strategy": "mdd",
  "item_ids": [101, 102, 103]
}
```
*Note : Si `item_ids` est omis ou vide, tous les articles non cochés de la liste sont inclus par défaut.*

#### Response 201 Created
```json
{
  "id": 42,
  "store": "leclerc",
  "external_store_id": "0123",
  "status": "reviewing",
  "optimization_strategy": "mdd",
  "items_count": 3,
  "matched_count": 2,
  "substitutes_count": 1,
  "unmatched_count": 0,
  "estimated_total_cents": 1450,
  "items": [
    {
      "id": 1,
      "grocery_item_id": 101,
      "cache_id": 554,
      "external_id": "LEC_BEURRE_250",
      "name": "Beurre doux Marque Repère 250g",
      "brand": "Marque Repère",
      "quantity": 1.0,
      "unit_price_cents": 210,
      "total_price_cents": 210,
      "match_type": "mdd",
      "status": "staged",
      "custom_note": null,
      "substitute_proposal": null
    },
    {
      "id": 2,
      "grocery_item_id": 102,
      "cache_id": 589,
      "external_id": "LEC_OEUF_BIO_6",
      "name": "Oeufs Frais Plein Air x6",
      "brand": "Marque Repère",
      "quantity": 2.0,
      "unit_price_cents": 240,
      "total_price_cents": 480,
      "match_type": "substitute",
      "status": "staged",
      "custom_note": null,
      "substitute_proposal": {
        "id": 10,
        "alternative_cache_id": 589,
        "alternative_name": "Oeufs Frais Plein Air x6",
        "alternative_brand": "Marque Repère",
        "price_difference_cents": 20,
        "reason": "Oeufs standard en rupture, substitut en plein air proposé (+0.20€)",
        "status": "pending"
      }
    }
  ]
}
```

---

## 2. Consultation d'un Job de Panier

### `GET /api/v1/supermarket/cart/jobs/{id}`
Récupère le détail du panier en cours de revue avec tous ses articles et propositions de substitution.

#### Response 200 OK
Structure identique à la réponse de création ci-dessus.

---

## 3. Mise à Jour Groupée des Articles Ajustés (Refinement LLM)

### `POST /api/v1/supermarket/cart/jobs/{id}/refine`
Transmet au LLM en tâche de fond la liste des ajustements saisis par l'utilisateur (remarques textuelles, suppressions, choix de substituts) et recalcule le panier.

#### Request Body
```json
{
  "adjustments": [
    {
      "matched_item_id": 2,
      "action": "accept_substitute",
      "substitute_id": 10
    },
    {
      "matched_item_id": 1,
      "action": "modify_with_note",
      "custom_note": "Prendre en format demi-sel 500g si possible"
    },
    {
      "matched_item_id": 3,
      "action": "remove"
    }
  ]
}
```

#### Response 200 OK
Retourne l'état réactualisé du job (`GroceryToCartJobRead`) après recalcul des correspondances par le LLM.

---

## 4. Validation Finale et Synchronisation Distante

### `POST /api/v1/supermarket/cart/jobs/{id}/sync`
Transfère en un seul appel groupé tous les articles validés du job vers le panier distant du supermarché (`SupermarketCart`).

#### Response 200 OK
```json
{
  "id": 42,
  "status": "synced",
  "synced_at": "2026-09-13T12:05:00Z",
  "remote_cart_ref": "cart_session_88912",
  "items_synced_count": 2,
  "message": "Panier transféré avec succès sur le drive distant en statut brouillon prêt pour retrait."
}
```
*Effet de bord immédiat* : Les `GroceryItem`s associés prennent `in_cart = True` (`checked = False`). Le garde-manger n'est PAS modifié.

---

## 5. Confirmation du Retrait Physique & Réapprovisionnement du Garde-Manger

### `POST /api/v1/supermarket/cart/jobs/{id}/confirm-pickup`
Déclenché par l'utilisateur une fois la commande récupérée au drive. Coche tous les articles en bloc et génère les écritures `GroceryPantrySync`.

#### Response 200 OK
```json
{
  "id": 42,
  "status": "completed",
  "completed_at": "2026-09-13T14:30:00Z",
  "restocked_items_count": 2,
  "message": "Courses confirmées retirées. 2 articles ajoutés au garde-manger."
}
```
*Effet de bord immédiat* : Les `GroceryItem`s associés prennent `checked = True`. Les enregistrements `GroceryPantrySync` correspondants sont créés et les stocks de `PantryItem` sont incrémentés (Principe III).
