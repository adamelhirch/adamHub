# Technical Research: Sélection du Magasin Drive et Synchronisation du Panier

**Branch**: `004-supermarket-drive-store-selection-cart-sync`
**Feature Directory**: `specs/004-supermarket-drive-store-selection-cart-sync`
**Date**: 2026-09-13

---

## 1. Recherche et Typologie des Points de Retrait (Leclerc, Auchan, Carrefour, Intermarché)

### Decision
Implémenter un service unifié de localisation `SupermarketStoreLocator` composé de 4 adaptateurs spécialisés (`app/services/scrapers/`):
- **Auchan** : Réutilisation de `list_auchan_offering_contexts` (`app/services/scrapers/auchan.py`) qui interroge l'API de localisation Auchan avec code postal, ville et coordonnées GPS.
- **Leclerc** : Interrogation de l'API de géolocalisation des points de retrait Leclerc (`e.leclerc/api/rest/search/store` ou scraping de l'annuaire des drives). Retourne explicitement la typologie : Quai Drive standard, Spot Drive urbain déporté, Borne automatique TAPE (Terminal Automatique de Prise d'Effets) et Drive Piéton.
- **Carrefour** : Interrogation de l'API de géolocalisation des magasins Carrefour (`carrefour.fr/api/magasins`), filtrant les points de collecte avec services actifs (`hasDrive`, `hasDrivePieton`).
- **Intermarché** : Interrogation de l'API point de vente (`intermarche.com/api/pdv/search`), résolvant le `pdvId` et les types de retrait disponibles.

### Rationale
Les prix, promotions et disponibilités de stock varient d'un entrepôt drive à l'autre. La normalisation vers un schéma commun `SupermarketStoreLocation` (`store`, `external_store_id`, `name`, `address`, `zipcode`, `city`, `pickup_type`, `distance_km`, `channel`) permet aux clients Web et Mobile d'utiliser une seule interface pour toutes les enseignes.

### Alternatives Considered
- *Forcer l'utilisateur à saisir manuellement son identifiant de magasin* : Rejeté, car trop technique et source d'erreurs.
- *Scraper uniquement les pages HTML complètes à chaque recherche de magasin* : Rejeté, car trop lent (>5s) et vulnérable aux blocages anti-bot par rapport aux endpoints JSON de localisation légers ou caches locaux.

---

## 2. Modèle de Données et Cloisonnement Multi-Tenant (Principe I)

### Decision
Migrer l'entité de sélection de magasin existante (`SupermarketStoreSelection`) vers une entité isolée par tenant : `UserStorePreference`.
- Clé étrangère indexée `user_id: int = Field(foreign_key="user.id", index=True)`.
- Contrainte d'unicité composée `(user_id, store)`.
- Stockage de la typologie de retrait (`pickup_type`: `quai`, `spot`, `tape`, `pieton`).
- Stockage de la stratégie d'optimisation par défaut de l'utilisateur (`optimization_strategy`: `mdd`, `budget`, `bio`).

### Rationale
La table existante `SupermarketStoreSelection` avait une contrainte `unique=True` sur le champ `store` sans `user_id`, ce qui limitait l'ensemble de la plateforme à un seul magasin partagé pour tous les utilisateurs. Cela violait le Principe I de la Constitution ("Strict Multi-Tenant Data Isolation"). Le nouveau modèle garantit une étanchéité complète entre comptes.

### Alternatives Considered
- *Conserver la table globale et ajouter une table de mapping `UserStore`* : Rejeté, complexité inutile avec jointures superflues alors que la préférence appartient directement au tenant.

---

## 3. Algorithme de Résolution d'Ingrédients Génériques & Stratégies d'Optimisation

### Decision
Mettre en place un pipeline de résolution en 3 étapes dans `app/services/supermarket/cart_matcher.py` :
1. **Étape 1 : Historique validé (Priorité 1)**
   - Vérifier si l'utilisateur a déjà acheté ou validé une correspondance pour cet ingrédient générique auprès de ce drive (`SupermarketMapping` ou `MatchedCartItem` antérieur du même tenant). Si oui, la référence exacte est réutilisée.
2. **Étape 2 : Recherche & Stratégie d'Optimisation (Priorité 2)**
   - Si aucune correspondance historique n'existe, interroger le catalogue réel du drive (`SupermarketSearchCache`).
   - Appliquer la stratégie d'optimisation choisie :
     - `MDD / Qualité-Prix` (par défaut) : Privilégie les marques distributeurs (Marque Repère pour Leclerc, Auchan pour Auchan, Carrefour Classic' pour Carrefour, Monique Ranou/Pâturages pour Intermarché) au format le plus proche.
     - `Budget strict` : Sélectionne le produit offrant le prix unitaire (€/kg ou €/L) le plus faible.
     - `Bio / Qualité` : Filtre ou sur-pondère les labels biologiques et marques reconnues.
3. **Étape 3 : Détection des ruptures & Substitutions**
   - Si le produit habituel est en rupture de stock, sélectionner le meilleur substitut de même catégorie et contenance, générer une `SubstituteProposal` avec différentiel de prix chiffré.
   - Si aucun produit ne correspond, classer en `UnmatchedGroceryItem` (maintenu sur la liste locale sans être envoyé au drive).

### Rationale
Cette approche minimise le nombre d'ajustements manuels nécessaires pour l'utilisateur tout en garantissant un panier économique et sans produits farfelus ou non désirés.

### Alternatives Considered
- *Confier la totalité du matching à un prompt LLM sans validation sur catalogue réel* : Strictement rejeté par le Principe II ("Truth-in-Store Retail Data - Store-backed items MUST originate from genuine retailer product data recorded in SupermarketSearchCache, NEVER from client-fabricated or mocked metadata").

---

## 4. Architecture de Staging Local (`GroceryToCartJob`)

### Decision
Créer une entité de staging local :
- `GroceryToCartJob` : `id`, `user_id`, `store`, `external_store_id`, `status` (`draft`, `reviewing`, `syncing`, `synced`, `failed`), `items_count`, `estimated_total_cents`, `created_at`, `updated_at`.
- `MatchedCartItem` : `id`, `job_id`, `grocery_item_id`, `cache_id`, `external_id`, `name`, `brand`, `quantity`, `unit_price_cents`, `total_price_cents`, `match_type` (`exact_history`, `mdd`, `budget`, `substitute`), `status` (`staged`, `to_modify`, `removed`, `synced`), `custom_note`.
- `SubstituteProposal` : `id`, `matched_item_id`, `alternative_cache_id`, `reason`, `price_difference_cents`, `status` (`pending`, `accepted`, `rejected`).

### Rationale
Valide la décision de clarification (Question 1) : tout est préparé localement dans AdamHUB avant tout appel vers les APIs distantes des supermarchés. Cela élimine les risques de blocage anti-bot, évite de surcharger les sessions et assure une expérience de prévisualisation instantanée.

---

## 5. Ergonomie des Gestes Swipe & Affinement en Tâche de Fond

### Decision
- **Composant UI Mobile (`app-saas/`)** : Réutilisation de la bibliothèque de gestes `react-native-gesture-handler` (`Swipeable`), déjà mise en place pour les recettes (`recipe-card-swipeable.tsx`).
  - *Swipe gauche/droite* : Action de suppression (retire l'article du job brouillon).
  - *Swipe inverse* : Ouvre le modal de modification (affiche 2 à 3 alternatives directes issues du catalogue et un champ texte pour consigne au LLM).
  - *Marquage* : L'article prend visuellement le badge `"À modifier"`.
- **Bouton de mise à jour groupée** : Bouton *"Mettre à jour le panier"* qui envoie l'ensemble des consignes au backend (`POST /api/v1/supermarket/cart/jobs/{id}/refine`).
- **Exécution LLM en background** : Le backend déclenche un appel LLM qui reformule les requêtes de recherche et sélectionne les nouveaux produits de remplacement, mettant à jour le job de staging sans quitter l'écran de courses.

---

## 6. Statut d'Article et Réapprovisionnement Invariant du Garde-Manger (Principe III)

### Decision
- Lors de la synchronisation réussie vers le panier distant du commerçant, les articles de la liste de courses prennent le statut `status = "in_cart"` (`checked = False`). Aucun enregistrement `GroceryPantrySync` n'est créé à cette étape.
- Un endpoint dédié `POST /api/v1/supermarket/cart/jobs/{id}/confirm-pickup` est appelé lors de l'action utilisateur *"Confirmer le retrait des courses"* :
  1. Passe `checked = True` sur chaque `GroceryItem` lié au job.
  2. Crée les liaisons `GroceryPantrySync` (`grocery_item_id`, `pantry_item_id`, `added_quantity`).
  3. Incrémente les stocks des `PantryItem` correspondants.
  4. Marque le job en `status = "completed"`.

### Rationale
Respecte rigoureusement le Principe III de la Constitution en interdisant toute modification prématurée des stocks du garde-manger avant le retrait physique réel de la commande au supermarché.
