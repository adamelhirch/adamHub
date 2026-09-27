# Supermarket Drive Store Selection & Cart Synchronization

Ce guide documente le fonctionnement complet du module de sélection de magasin drive, de préparation de panier et de synchronisation pour AdamHUB.

---

## 1. Vue d'ensemble

Le module Drive Supermarché permet à l'utilisateur :
1. **De configurer son magasin Drive favori** pour chaque grande enseigne française (E.Leclerc, Auchan, Carrefour, Intermarché), en précisant la typologie de retrait (`quai`, `spot`, `tape`, `pieton`) et sa stratégie d'optimisation par défaut (`mdd`, `budget`, `bio`).
2. **De préparer un panier drive** directement depuis sa liste de courses (« Préparer mon Drive »). Cette action génère un panier de pré-validation local (`GroceryToCartJob`) qui associe chaque article générique à un produit réel du magasin via le moteur de correspondance multi-critères (`CartMatcherService`).
3. **De réviser interactivement le panier** via des gestes tactiles :
   - **Swipe vers la gauche** : supprimer un article du panier.
   - **Swipe vers la droite** : ouvrir le modal de modification (sélection d'alternatives ou saisie d'une consigne textuelle personnalisée pour l'IA).
   - **Bouton « Mettre à jour le panier »** : soumettre en tâche de fond les ajustements et consignes textuelles au LLM pour raffinement par lot.
4. **De synchroniser vers l'enseigne distante** :
   - Envoi du panier finalisé vers le panier distant en statut brouillon (`draft`).
   - Les articles de course passent en statut `in_cart = True` et `checked = False`.
   - **Aucun impact sur le garde-manger à cette étape** (respect absolu du Principe Fondateur III).
5. **De confirmer le retrait physique** :
   - Le bouton « Confirmer le retrait » marque les articles de course comme `checked = True`.
   - Les articles sont automatiquement ajoutés / incrémentés dans le garde-manger (`PantryItem`) via `GroceryPantrySync`.

---

## 2. Principes Fondateurs & Invariants

Ce module applique rigoureusement les principes de la Constitution AdamHUB :
- **Principe I - Isolation Multi-Tenant Stricte** : Chaque préférence (`UserStorePreference`), job de panier (`GroceryToCartJob`) et ligne de panier (`MatchedCartItem`) est strictement cloisonné par `user_id`. Toute tentative d'accès cross-tenant génère un code HTTP 404.
- **Principe II - Vérité Magasin & Non-Invention** : Tous les prix, références SKU (`external_id`) et emballages proviennent impérativement du catalogue de recherche authentique (`SupermarketSearchCache`). L'IA n'invente jamais de données tarifaires ou de produits fictifs.
- **Principe III - Respect du Cycle de Vie des Stocks** : La synchronisation du panier drive n'est pas un achat finalisé. Les stocks du garde-manger ne sont incrémentés **qu'au moment de la confirmation physique du retrait** (`confirm-pickup`).

---

## 3. Modèle de Données

### `UserStorePreference`
- `id`: Identifiant unique.
- `user_id`: Identifiant du locataire propriétaire.
- `store`: Enseigne (`leclerc`, `carrefour`, `intermarche`, `auchan`).
- `external_store_id`: Code identifiant du magasin (ex: `01234` pour Leclerc, `12345` pour Intermarché).
- `store_label`: Libellé lisible (ex: « E.Leclerc Roques »).
- `location_label`: Adresse ou code postal.
- `pickup_type`: Typologie (`quai`, `spot`, `tape`, `pieton`).
- `optimization_strategy`: Stratégie (`mdd`, `budget`, `bio`).
- `channel`: Canal de distribution (`drive`, `express`, etc.).

### `GroceryToCartJob`
- `id`: Identifiant du job.
- `user_id`: Utilisateur propriétaire.
- `store`: Enseigne ciblée.
- `external_store_id`: Magasin sélectionné.
- `status`: Statut (`pending`, `reviewing`, `syncing`, `completed`, `failed`).
- `optimization_strategy`: Stratégie appliquée.
- `items_count`, `matched_count`, `substitutes_count`, `unmatched_count`: Métriques du panier.
- `estimated_total_cents`: Montant estimé en centimes.

### `MatchedCartItem`
- `id`: Identifiant de la ligne.
- `job_id`: Job parent.
- `grocery_item_id`: Article source de la liste de courses.
- `cache_id`: Référence vers `SupermarketSearchCache`.
- `external_id`: SKU distant du produit.
- `name`, `brand`, `packaging`, `image_url`: Métadonnées authentiques du produit.
- `quantity`, `unit_price_cents`, `total_price_cents`: Données tarifaires.
- `match_type`: Type d'association (`exact_history`, `mdd`, `budget`, `substitute`).
- `status`: Statut d'approbation (`staged`, `modified`, `removed`).
- `custom_note`: Consigne textuelle de l'utilisateur pour l'IA.

---

## 4. Endpoints API REST

Base URL : `/api/v1/supermarket`

| Méthode | Route | Description |
| :--- | :--- | :--- |
| `GET` | `/stores/search` | Recherche les magasins physiques par code postal ou ville |
| `GET` | `/stores/preferences` | Récupère les magasins favoris configurés pour l'utilisateur |
| `PUT` | `/stores/preferences/{store}` | Enregistre ou met à jour le magasin favori pour une enseigne |
| `POST` | `/cart/jobs` | Crée un job de panier drive (`status: reviewing`) |
| `GET` | `/cart/jobs/{id}` | Récupère le détail d'un job avec la liste des produits associés |
| `PATCH`| `/cart/jobs/{id}/items/{item_id}` | Met à jour une ligne (changement de produit, quantité ou statut) |
| `POST` | `/cart/jobs/{id}/refine` | Traite par lot les modifications et consignes textuelles |
| `POST` | `/cart/jobs/{id}/sync` | Pousse le panier vers l'enseigne (`in_cart = True`, `checked = False`) |
| `POST` | `/cart/jobs/{id}/confirm-pickup`| Confirme le retrait physique (`checked = True`, réapprovisionnement garde-manger) |

---

## 5. Pilotage par l'Assistant IA & MCP

L'assistant vocal/texte et le serveur MCP disposent de 5 outils dédiés :

1. **`supermarket.search_stores`**
   - Paramètres : `store` (optionnel), `zipcode`, `city`, `latitude`, `longitude`.
   - Permet de chercher les magasins et points de retrait disponibles.
2. **`supermarket.set_favorite_store`**
   - Paramètres : `store`, `external_store_id`, `store_label`, `location_label`, `pickup_type`, `optimization_strategy`.
   - Enregistre le magasin drive favori de l'utilisateur.
3. **`supermarket.prepare_cart`**
   - Paramètres : `store` (optionnel), `optimization_strategy` (optionnel), `external_store_id` (optionnel), `item_ids` (optionnel).
   - Génère un staging draft et renvoie le bilan synthétique (total estimé, nombre d'articles associés, substituts).
4. **`supermarket.confirm_cart_sync`**
   - Paramètres : `job_id`.
   - Pousse le panier vers l'enseigne distante sans toucher au garde-manger.
5. **`supermarket.confirm_pickup`**
   - Paramètres : `job_id`.
   - Valide la réception des courses et alimente automatiquement les stocks du garde-manger.

---

## 6. Interfaces Utilisateur

### Application Mobile (React Native / Expo SaaS)
- **Déclenchement** : Bouton « Préparer mon Drive » dans l'en-tête de l'écran Courses (`app-saas/src/app/(tabs)/kitchen.tsx`).
- **Sélection de Magasin** : `SupermarketStoreModal` permettant de chercher par code postal, de choisir son point de retrait (`quai`, `spot`, `tape`, `pieton`) et sa stratégie d'optimisation.
- **Révision Tactile** : `CartReviewModal` affichant chaque article avec le composant swipeable `CartItemSwipeable`.
  - Swipe gauche : suppression immédiate.
  - Swipe droite : ouverture du modal `CartItemEditModal` pour choisir une alternative ou taper une consigne ("Je préfère sans gluten", "Marque Repère uniquement").
- **Actions de Finalisation** : Bouton « Mettre à jour » pour le recalcule, bouton « Valider et synchroniser », et bouton « Confirmer le retrait » une fois la commande récupérée.

### Application Web (React / Tailwind)
- Intégré dans la page `GroceriesPage.tsx`.
- Modale de sélection de magasin `SupermarketStoreSelector.tsx`.
- Tiroir latéral de revue `CartReviewPanel.tsx` offrant le remplacement d'articles, la saisie de consignes de raffinement et la synchronisation.
