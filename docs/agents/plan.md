# Plan — adamHub — 2026-08-16 — Run B : Miroir panier réel Intermarché (pilote)

## Objective
Faire du panier Intermarché d'AdamHUB le **miroir du vrai panier sur intermarche.com** :
manipuler le panier depuis AdamHUB (ajouter, modifier la quantité, supprimer, vider) agit sur
le vrai panier du site, et le panier local reflète l'état du site après chaque action. Pilote
sur Intermarché ; les 3 autres enseignes suivront selon le même modèle.

## Context
- **API panier Intermarché** (extraite du `.har` `/Users/adamelhirch/Downloads/intermarche.har`) :
  - `POST /api/service/panier/v1/stores/{store_id}/carts` — body
    `{"customerDateTime":..., "events":[{"catalog":"PDV","itemId":...,"quantity":...,
    "type":"QUANTITY","acceptSubstitution":true}], "lastSynchronizedCart":{...}}`.
    `quantity: +1` ajoute, `+n` modifie, **`-1` supprime**. La réponse = le panier complet
    (items `{id, quantity, price, amount, item:{itemId, libelle, prix, ...}}`, `amount`,
    `itemsNumber`).
  - `DELETE /api/service/panier/v1/customers/{customer_uuid}/carts` → 204 (vider).
  - Pas de GET API : la lecture se fait via les réponses des POST (chaque POST rejoue
    `lastSynchronizedCart` — mécanisme de concurrence).
  - `customer_uuid` = `515ffd9e-538e-447a-983e-69ca17363fac` (session) ; `store_id` = `11131`.
- **store_id Intermarché** : cookie `itm_pdv` = `{"ref":"11131","name":"Super Ramonville
  Saint-Agne",...}` — `extract_pdv_ref_from_cookies` (`app/services/scrapers/intermarche.py:108`)
  le récupère déjà (fallback `novaParams.pdvRef`). Pas de sélection persistée Intermarché
  (`SupermarketStoreSelection` n'est alimentée que par Auchan) — le cookie reste la source,
  la persistance viendra au run sélecteurs.
- **Session** : cookies importés (`SupermarketConnection`, chiffrés Fernet), même chemin que la
  recherche (`load_active_cookies` / fallback `data/cookies_intermarche.json`).
- **Paniers locaux** (Run 1, tables `SupermarketCart`/`SupermarketCartItem` + endpoints
  `/supermarket/carts*`) existent — ils deviennent le **reflet** du site, pas une source
  indépendante.
- Références : `app/services/scrapers/intermarche.py`, `app/services/store_catalog.py`,
  `app/services/cart.py` (Run 1), `app/api/endpoints/supermarket.py`,
  `web/src/pages/GroceriesPage.tsx` (onglet Panier), `web/src/store/groceryStore.ts`,
  `data/cookies_intermarche.json`.

## Decisions
- **Source de vérité = le site** : chaque action AdamHUB → POST/DELETE au vrai panier → la
  réponse du site écrase le panier local (`SupermarketCart`+items). Le local est le dernier
  état connu du site.
- **Les 4 actions** : ajouter (+1), modifier quantité (+n), supprimer (-1 via event quantity=-1),
  vider (DELETE carts).
- **store_id** : `extract_pdv_ref_from_cookies` sur les cookies de la connection active (ref =
  store_id). Fallback futur : SupermarketStoreSelection (run sélecteurs).
- **Session** : cookies importés (SupermarketConnection active), httpx (même mécanique que la
  recherche Intermarché — qui ne pose pas de challenge). Pas de proxy ce run (la recherche
  Intermarché passe en direct).
- **Réconciliation** : réponse du site = état local ; le panier local est réécrit intégralement
  à chaque action réussie.
- **Échec d'action** (session morte, 4xx, DataDome) : rejet + message clair dans l'UI, le local
  n'est pas modifié, l'utilisateur est invité à resynchroniser ses cookies.
- **UI web** : l'onglet « Panier » existant (GroceriesPage) reflète le panier réel Intermarché ;
  les actions (ajouter/quantité/supprimer/vider) appellent le site via le backend ; total/items
  viennent de la réponse du site.
- **Tests** : backend pytest TDD (adapter panier + endpoint mirror), web = gate lint+build.
  CI-green + squash-merge (tracker github).
- Le panier local continue de servir les 3 autres enseignes (mode local du Run 1) tant que leur
  miroir réel n'est pas branché — Intermarché seul bascule en miroir réel ce run.

## Out of scope
- Miroir panier réel des 3 autres enseignes (Carrefour, Leclerc, Auchan) → runs suivants.
- Sélecteur de magasin Intermarché persisté (SupermarketStoreSelection) → run sélecteurs.
- Paniers sur app-saas (mobile + web Expo).
- Actualisation automatique des prix du panier (le prix vient du site à chaque action).

## Tasks

### b1: Backend — adapter panier Intermarché (lecture/écriture du vrai panier)
- spec: Créer l'adapter `app/services/scrapers/intermarche_cart.py` (ou `app/services/cart_sync/`)
  qui parle à l'API panier Intermarché avec les cookies de la connection active :
  `get_or_read_cart` (via POST avec events vides + lastSynchronizedCart, ou reflet de la dernière
  réponse), `add_item(itemId, qty)`, `update_item_quantity(itemId, qty)`, `remove_item(itemId)`
  (event quantity=-1), `clear_cart` (DELETE customers/{uuid}/carts). Récupérer le `store_id`
  via `extract_pdv_ref_from_cookies` et le `customer_uuid` depuis la session (le .har le
  contient : 515ffd9e-...). Construire le body conforme (customerDateTime, events,
  lastSynchronizedCart rejoué depuis l'état local). Normaliser la réponse du site en
  SupermarketCartItem (id, itemId, nom, prix, quantité, image si dispo). Gérer les erreurs
  (4xx/session morte) en exceptions claires. TDD : tests unitaires de l'adapter (mock httpx,
  fixtures .har réduites), test de mapping réponse→items, test des 4 actions + clear, test
  d'erreur session.
- blocked-by: none
- agent: worker
- isolated: yes

### b2: Backend — endpoint miroir (brancher sur /supermarket/carts Intermarché)
- spec: Faire que les endpoints `/supermarket/carts*` existants (Run 1) basculent en mode
  **miroir réel pour Intermarché** : POST items (ajout) → appel adapter add_item + réécrit le
  panier local depuis la réponse ; PATCH quantity → update_item_quantity ; DELETE item →
  remove_item ; DELETE cart → clear_cart. GET /carts/{store} → relit le panier depuis le site
  (POST events vides) si store=intermarche, sinon lit le local. PUT status (validation manuelle)
  inchangé (local). Chaque action réussie écrase le local ; chaque échec rejette avec un
  message clair sans toucher le local. Tenant `CurrentOrOwnerUser`. TDD : tests des endpoints
  miroir (monkeypatch adapter), tests de rejet sur erreur session, non-régression des endpoints
  locaux pour les 3 autres enseignes.
- blocked-by: b1
- agent: worker
- isolated: yes

### b3: Web — l'onglet Panier reflète le panier réel Intermarché
- spec: Dans `web/src/pages/GroceriesPage.tsx` + `web/src/store/groceryStore.ts` : l'onglet
  Panier Intermarché affiche le panier réel (chargé via GET /supermarket/carts/intermarche) ;
  les actions add/quantité/supprimer/vider appellent les endpoints miroir et l'UI re-rend le
  résultat renvoyé par le site (total, items, quantités). Afficher un état « synchro avec le
  site » et, en cas d'erreur (session morte), un message clair invitant à resynchroniser les
  cookies dans l'extension. Les 3 autres enseignes gardent le comportement local du Run 1.
  Gate : `cd web && npm run lint && npm run build`.
- blocked-by: b2
- agent: worker
- isolated: yes

### b4: Validation de bout en bout du miroir panier
- spec: Valider le flux complet : avec les cookies Intermarché connectés, depuis le backend,
  ajouter un article → vérifier qu'il apparaît sur intermarche.com ET dans le local ; modifier
  la quantité ; supprimer ; vider ; vérifier que le panier local reflète chaque état. `uv run
  pytest` vert + smoke manuel documenté. Rapport `docs/agents/report-b-validation.md`.
  Signalement clair des résultats (actions + états du site vs local).
- blocked-by: b3
- agent: worker
- isolated: yes

## Status
approved — 2026-08-16
