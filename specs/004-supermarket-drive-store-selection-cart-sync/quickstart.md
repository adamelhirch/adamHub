# Quickstart & Validation Guide: Sélection du Magasin Drive et Synchronisation du Panier

**Branch**: `004-supermarket-drive-store-selection-cart-sync`
**Date**: 2026-09-13
**Feature Spec**: `specs/004-supermarket-drive-store-selection-cart-sync/spec.md`

Ce guide détaille les scénarios de validation pas à pas pour tester l'ensemble du flux de sélection de drive, de préparation de panier et de réapprovisionnement.

---

## Prérequis

1. Backend démarré sur `http://localhost:8000` avec virtualenv uv :
   ```bash
   uv run uvicorn app.main:app --reload
   ```
2. Un utilisateur actif enregistré avec son token JWT ou clé API.
3. Des articles de courses présents sur la liste (ex. `Beurre`, `Oeufs`, `Lait`, `Poulet`).

---

## Scénario 1 : Recherche et Configuration du Point de Retrait Drive (FR-001, FR-002, FR-003)

### 1.1 Rechercher les magasins à proximité
```bash
curl -X GET "http://localhost:8000/api/v1/supermarket/stores/search?zipcode=31700&city=Blagnac" \
  -H "Authorization: Bearer <TOKEN>"
```
**Résultat attendu** :
- Liste ordonnée de magasins (Leclerc, Auchan, Carrefour, Intermarché) avec adresses, distances et le type précis (`pickup_type`: `quai`, `spot`, `tape`, `pieton`).

### 1.2 Enregistrer son drive favori (avec borne TAPE)
```bash
curl -X PUT "http://localhost:8000/api/v1/supermarket/stores/preferences/leclerc" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "external_store_id": "0123_TAPE_1",
    "store_label": "Borne TAPE Leclerc Cornebarrieu",
    "location_label": "Route de Colomiers, 31700 Cornebarrieu",
    "pickup_type": "tape",
    "optimization_strategy": "mdd"
  }'
```
**Résultat attendu** :
- Réponse 200 OK avec la préférence enregistrée strictement pour l'utilisateur connecté (`user_id`).

---

## Scénario 2 : Génération du Panier Brouillon / Staging Local (FR-006, FR-013, FR-015)

### 2.1 Déclencher la préparation du panier depuis la vue Courses
```bash
curl -X POST "http://localhost:8000/api/v1/supermarket/cart/jobs" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "store": "leclerc",
    "optimization_strategy": "mdd"
  }'
```
**Résultat attendu** :
- Statut 201 Created avec `status: "reviewing"`.
- Chaque article de la liste de courses est résolu vers un produit authentique du catalogue réel (`SupermarketSearchCache`), avec son prix unitaire et ses quantités.
- Si un produit est indisponible, une `SubstituteProposal` est attachée avec justification et écart de prix.
- **Vérification clé** : Le panier distant chez Leclerc n'a PAS encore été altéré à cette étape (Principe II & Staging local).

---

## Scénario 3 : Revue Interactive, Gestes de Swipe & Affinement LLM (FR-016)

### 3.1 Simuler un swipe de modification avec consigne texte
```bash
curl -X POST "http://localhost:8000/api/v1/supermarket/cart/jobs/1/refine" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "adjustments": [
      {
        "matched_item_id": 1,
        "action": "modify_with_note",
        "custom_note": "Préférer du beurre demi-sel 500g"
      }
    ]
  }'
```
**Résultat attendu** :
- Le LLM en tâche de fond réévalue la requête et sélectionne la référence de beurre demi-sel 500g dans le catalogue réel.
- Le total estimé du panier est réactualisé immédiatement.

---

## Scénario 4 : Validation Finale & Synchronisation Distante (FR-013, FR-021)

### 4.1 Valider le panier et envoyer vers le drive commerçant
```bash
curl -X POST "http://localhost:8000/api/v1/supermarket/cart/jobs/1/sync" \
  -H "Authorization: Bearer <TOKEN>"
```
**Résultat attendu** :
- Réponse 200 OK avec `status: "synced"`.
- Le panier distant du commerçant (`SupermarketCart`) est alimenté via l'adaptateur de scraper en statut brouillon.
- Les articles correspondants dans `GroceryItem` passent à `in_cart = True` (`checked = False`).
- **Vérification Invariant (Principe III)** : Aucun article n'a été ajouté au garde-manger à ce stade !

---

## Scénario 5 : Retrait Physique & Réapprovisionnement Invariant (FR-021, Principe III)

### 5.1 Confirmer le retrait au drive
```bash
curl -X POST "http://localhost:8000/api/v1/supermarket/cart/jobs/1/confirm-pickup" \
  -H "Authorization: Bearer <TOKEN>"
```
**Résultat attendu** :
- Réponse 200 OK avec `status: "completed"`.
- Les `GroceryItem`s liés au job passent à `checked = True`.
- Des liaisons `GroceryPantrySync` sont créées avec les quantités réelles.
- Les stocks des `PantryItem` correspondants sont immédiatement crédités dans le garde-manger.

---

## Commandes de Tests Automatisés

- **Backend Unit & Integration Tests** :
  ```bash
  uv run --extra dev pytest tests/test_supermarket_store_locator.py tests/test_grocery_cart_job.py
  ```
- **Web SPA Validation** :
  ```bash
  cd web && npm run lint && npm run build
  ```
- **Mobile SaaS App Validation** :
  ```bash
  cd app-saas && npm run typecheck && npm run lint
  ```
