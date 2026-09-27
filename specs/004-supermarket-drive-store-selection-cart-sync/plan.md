# Implementation Plan: Sélection du Magasin Drive et Synchronisation du Panier depuis la Liste de Courses

**Branch**: `004-supermarket-drive-store-selection-cart-sync` | **Date**: 2026-09-13 | **Spec**: [spec.md](spec.md)

**Input**: Spécification fonctionnelle et clarifications interactives de `specs/004-supermarket-drive-store-selection-cart-sync/spec.md`.

---

## Summary

Permettre à chaque utilisateur de rechercher, sélectionner et enregistrer son magasin Drive favori (quai classique, spot déporté, borne automatique TAPE, drive piéton) pour chacune des 4 grandes enseignes (Leclerc, Auchan, Carrefour, Intermarché). Permettre ensuite de générer un panier Drive complet depuis la liste de courses via un bouton dédié sur l'écran Courses, en exécutant la résolution des correspondances et des substitutions par le LLM en tâche de fond dans un job de staging local (`GroceryToCartJob`). L'utilisateur ajuste les produits dans un panneau de revue interactif par gestes de swipe (identique à la planification de recettes) et notes textuelles, puis déclenche l'envoi groupé vers le panier distant du commerçant en statut brouillon. Une fois les courses physiquement récupérées, l'action "Confirmer le retrait" coche les articles et réapprovisionne le garde-manger conformément aux invariants de la Constitution.

---

## Technical Context

**Language/Version**: Python 3.12+ (Backend FastAPI), TypeScript 5.4+ (Web Vite & Mobile Expo React Native)

**Primary Dependencies**:
- Backend: FastAPI, SQLModel / SQLAlchemy 2.0, Pydantic v2, Alembic, HTTPX, OpenAI/Gemini SDK (LLM background resolution)
- Mobile SaaS (`app-saas/`): Expo 52, React Native 0.76, `react-native-gesture-handler` (Swipeable)
- Web (`web/`): React 18, Vite, Tailwind CSS, Lucide-react

**Storage**:
- PostgreSQL (prod) / SQLite (tests & local dev)
- Entités SQLModel : `UserStorePreference`, `GroceryToCartJob`, `MatchedCartItem`, `SubstituteProposal`, `SupermarketSearchCache`, `GroceryItem`, `GroceryPantrySync`

**Testing**:
- Backend: `uv run --extra dev pytest tests/test_supermarket_store_locator.py tests/test_grocery_cart_job.py`
- Web SPA: `cd web && npm run lint && npm run build`
- Mobile SaaS: `cd app-saas && npm run typecheck && npm run lint`

**Target Platform**: Multi-surface (FastAPI Web Service, Vite SPA Web, Expo iOS/Android Mobile App)

**Project Type**: Fullstack Web & Mobile Application + AI Assistant integration

**Performance Goals**:
- Recherche de magasins géolocalisés < 500ms
- Génération complète du panier de staging (20 articles) < 15s sous conditions réseau nominales
- Synchronisation groupée vers le panier distant < 5s

**Constraints**:
- Strict multi-tenant isolation (`user_id` obligatoire sur chaque entité persistante)
- Aucune donnée produit fictive ou inventée (Principe II)
- Aucun réapprovisionnement du garde-manger avant confirmation explicite du retrait physique (Principe III)
- Horodatages et slots exclusivement en UTC (Principe IV)
- Chiffrement Fernet des cookies et identifiants commerçants importés

**Scale/Scope**:
- 4 enseignes de grande distribution (Leclerc, Auchan, Carrefour, Intermarché)
- 4 typologies de points de retrait (quai, spot, TAPE, piéton)
- Staging local, revue interactive par swipe et mise à jour LLM en tâche de fond

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **Principle I: Strict Multi-Tenant Data Isolation & Dual-Mode Auth (NON-NEGOTIABLE)**
  - *Statut*: **PASS**
  - *Justification*: `UserStorePreference`, `GroceryToCartJob` et `MatchedCartItem` intègrent tous un champ `user_id: int` indexé et clé étrangère vers `User`. Les requêtes utilisent `CurrentOrOwnerUser` et retournent 404 (jamais 403) en cas de tentative d'accès cross-tenant.

- **Principle II: Truth-in-Store Retail Data & Live Mirroring**
  - *Statut*: **PASS**
  - *Justification*: Tous les articles appariés (`MatchedCartItem`) et propositions de substitution sont strictement adossés à une entrée réelle `cache_id` dans `SupermarketSearchCache`. Aucune donnée produit n'est fabriquée côté client. La synchronisation distante alimente le miroir `SupermarketCart` réconcilié avec la réponse du drive.

- **Principle III: Invariant-Driven Pantry & Grocery State Transitions**
  - *Statut*: **PASS**
  - *Justification*: Lors de la synchronisation du panier, les articles de la liste passent à `in_cart = True` mais restent **non cochés** (`checked = False`). Le réapprovisionnement du garde-manger (`GroceryPantrySync`) est strictement déclenché lors du clic sur l'action *"Confirmer le retrait des courses"* (`checked = True`), interdisant tout stock fantôme anticipé.

- **Principle IV: UTC Everywhere & Non-Bypassable Timeline Validation**
  - *Statut*: **PASS**
  - *Justification*: Toutes les dates de synchronisation, création de jobs et créneaux sont sérialisées et persistées en UTC standardisé (`default_factory=utcnow`).

- **Principle V: Test-First Quality Assurance & Contract Synchronization**
  - *Statut*: **PASS**
  - *Justification*: Synchronisation conjointe des schémas et endpoints FastAPI, des adaptateurs de scrapers, des actions assistant (`adamhub-assistant/SKILL.md`), de l'interface mobile (`app-saas/`) et des suites de tests automatisées `pytest`.

---

## Project Structure

### Documentation (this feature)

```text
specs/004-supermarket-drive-store-selection-cart-sync/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── store-locator-api.md
│   ├── cart-job-api.md
│   └── assistant-tools.md
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
app/
├── api/
│   └── endpoints/
│       └── supermarket.py       # Endpoints /stores/search, /stores/preferences, /cart/jobs
├── models/
│   └── entities.py              # UserStorePreference, GroceryToCartJob, MatchedCartItem, SubstituteProposal
├── schemas/
│   └── supermarket.py           # Pydantic schemas pour magasins, jobs de staging, ajustements et synchronisation
├── services/
│   ├── supermarket/
│   │   ├── store_locator.py     # Service unifié de recherche de magasins avec adaptateurs (Leclerc, Auchan, Carrefour, Intermarché)
│   │   ├── cart_matcher.py      # Résolution ingrédients génériques -> SKU réel selon stratégie (MDD, budget, bio)
│   │   └── cart_job_service.py  # Orchestration du staging local, ré-évaluation LLM et batch push
│   ├── scrapers/
│   │   ├── leclerc.py           # Adaptateur store locator Leclerc (Quai, Spot, TAPE, Piéton)
│   │   ├── auchan.py            # Adaptateur offering contexts Auchan
│   │   ├── carrefour.py         # Adaptateur store locator Carrefour
│   │   └── intermarche.py       # Adaptateur points de vente Intermarché
│   └── cart_mirror.py           # Synchronisation et réconciliation du panier distant
├── skill/
│   └── actions.py               # Assistant actions (supermarket.search_stores, prepare_cart, etc.)
└── mcp/
    └── server.py                # Outils MCP correspondants pour l'agent IA

app-saas/
├── src/
│   ├── app/
│   │   └── (tabs)/
│   │       └── kitchen.tsx      # Bouton "Préparer mon Drive" à côté de "Ajouter un article"
│   ├── components/
│   │   ├── supermarket-store-modal.tsx  # Modal de sélection magasin / enseigne type planification recette
│   │   ├── cart-review-modal.tsx        # Panneau de revue de panier avec affichage des correspondances
│   │   ├── cart-item-swipeable.tsx      # Ligne de produit avec swipe gauche (suppression) / swipe droite (modification)
│   │   └── cart-item-edit-modal.tsx     # Modal de substitution avec alternatives et consigne texte LLM
│   └── lib/
│       └── supermarket-api.ts   # Client API mobile pour stores et cart jobs

web/
└── src/
    ├── pages/
    │   └── GroceriesPage.tsx    # Intégration du bouton Drive et panneau de revue
    └── components/
        └── SupermarketStoreSelector.tsx

tests/
├── test_supermarket_store_locator.py  # Tests unitaires et intégration recherche magasins multi-enseignes
├── test_grocery_cart_job.py          # Tests du cycle de vie du staging, de la revue et du batch push
└── test_pantry_restock_invariant.py   # Tests d'intégrité du Principe III (restock au retrait uniquement)
```

**Structure Decision**: Architecture Fullstack existante d'AdamHUB respectant le découpage Single-Context : FastAPI backend avec SQLModel, SPA Vite `web/`, client mobile Expo `app-saas/`, et synchronisation des manifests d'assistant.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Aucun | N/A | L'architecture s'appuie directement sur les conventions et modèles existants sans ajouter de dépendance superflue. |
