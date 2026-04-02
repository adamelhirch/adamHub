# AdamHUB - Tour du projet et guide de reprise

Date d'audit: `2026-03-29`

Ce document sert de point de reprise pour les futures modifications. Il decrit l'architecture reelle du projet, les invariants metier importants, et les fichiers a toucher selon le type de changement.

## 1. Snapshot

- Backend FastAPI: `app/`
- Frontend React/Vite: `web/`
- Pack assistant: `app/skill/actions.py` + `adamhub-assistant/`
- Routes REST: `110`
- Actions skill: `99`
- Pages front: `6`

## 2. Structure du repo

### Backend

- `app/main.py`
  - boot FastAPI
  - CORS
  - montage du build frontend
  - scheduler lifecycle

- `app/api/`
  - un routeur par domaine
  - `router.py` agrege tout sous `/api/v1`

- `app/models/entities.py`
  - tables SQLModel
  - enums partages
  - centre de gravite des donnees metier

- `app/schemas/dto.py`
  - contrats REST et skill
  - a modifier quand la surface publique change

- `app/services/`
  - logique metier transverse
  - synchronisations calendrier / groceries / pantry / recipes / fitness / supermarket / video

- `app/skill/actions.py`
  - catalogue des actions exposees a l'assistant
  - mapping action -> execution
  - doit rester aligne avec les schemas et les services

### Frontend

- `web/src/App.tsx`
  - shell principal
  - navigation mobile/desktop
  - routing des 6 pages

- `web/src/pages/`
  - `CalendarPage.tsx`
  - `TasksPage.tsx`
    - onglet `Tâches` pour le ponctuel
    - onglet `Routine` pour les habitudes récurrentes
  - `FinancesPage.tsx`
  - `GroceriesPage.tsx`
  - `RecipesPage.tsx`
  - `FitnessPage.tsx`

- `web/src/store/`
  - stores orientes domaine
  - encapsulent les appels API et le state front

### IA / assistant

- `adamhub-assistant/SKILL.md`
  - skill maitre

- `adamhub-assistant/references/`
  - catalogue d'actions
  - exemples HTTP
  - playbooks multi-etapes

- `adamhub-assistant/`
  - skill maitre + skills domaine a plat

### Tests

- `tests/test_skill.py`
  - verifie le manifest et des executions skill

- `tests/test_calendar_overlap.py`
  - verrouille les conflits de planning

- `tests/test_grocery_pantry_flow.py`
  - synchronisation groceries <-> pantry

- `tests/test_meal_plan_calendar_flow.py`
  - repas / courses / calendrier

- `tests/test_fitness.py`
  - structure des exercices et projection calendrier

- `tests/test_video_intake.py`
  - transcript, metadata, fallback whisper

## 3. Domaines et fichiers a toucher

### Calendrier

But: timeline unifiee pour taches, repas, abonnements, events, fitness et items manuels.

Backend:

- `app/api/calendar.py`
- `app/services/calendar_hub.py`
- validateurs de conflit dans:
  - `app/api/tasks.py`
  - `app/api/events.py`
  - `app/api/subscriptions.py`
  - `app/api/meal_plans.py`
  - `app/api/fitness.py`

Frontend:

- `web/src/pages/CalendarPage.tsx`
- `web/src/components/DraggableTask.tsx`
- `web/src/components/DraggableCalendarItem.tsx`
- `web/src/components/DroppableSlot.tsx`
- `web/src/store/taskStore.ts`

Tests:

- `tests/test_calendar_overlap.py`
- `tests/test_meal_plan_calendar_flow.py`

Invariant critique:

- aucun element planifie ne doit chevaucher un autre element planifie sur le meme creneau
- tout est pense en UTC cote backend
- le front doit eviter les glissements de timezone au parsing

### Courses / garde-manger / supermarche

But: rechercher un produit magasin, lier un produit choisi, gerer groceries et pantry sans inventer de metadata magasin.

Backend:

- `app/api/groceries.py`
- `app/api/pantry.py`
- `app/api/endpoints/supermarket.py`
- `app/services/grocery_pantry.py`
- `app/services/scraper_service.py`
- `app/services/supermarket_mapping.py`
- `app/services/supermarket_registry.py`
- `app/services/scrapers/intermarche.py`

Frontend:

- `web/src/pages/GroceriesPage.tsx`
- `web/src/store/groceryStore.ts`

Tests:

- `tests/test_grocery_pantry_flow.py`
- `tests/test_supermarket.py`

Invariants critiques:

- un item "store-backed" doit provenir d'une recherche magasin valide
- fallback autorise: item generique sans metadata magasin
- cocher un grocery peut alimenter le pantry
- mapping magasin durable sur `RecipeIngredient` et `PantryItem`
- cache de recherche court, mapping durable

### Recettes / repas

But: recettes manuelles, ingredients custom ou magasin, planification, soustraction du garde-manger une fois cuisinee.

Backend:

- `app/api/recipes.py`
- `app/api/meal_plans.py`
- `app/services/meal_planning.py`
- `app/services/life.py` pour certaines vues agregees

Frontend:

- `web/src/pages/RecipesPage.tsx`

Tests:

- `tests/test_meal_plan_calendar_flow.py`

Invariants critiques:

- l'ajout d'une recette reste manuel cote front
- `video.fetch` sert a l'agent, pas a l'UI
- `meal_plan.add` planifie seulement
- `meal_plan.confirm_cooked` et `recipe.confirm_cooked` consomment le pantry
- `meal_plan.unconfirm_cooked` restaure la consommation precedente

### Video intake

But: donner a l'assistant transcript + metadata pour YouTube / Instagram / TikTok.

Backend:

- `app/api/video.py`
- `app/services/video_intake.py`

Tests:

- `tests/test_video_intake.py`

Invariant critique:

- le backend ne transforme pas la video en recette
- l'extraction retourne la matiere premiere: transcript, segments, metadata, warnings
- fallback local `faster-whisper` si captions indisponibles

### Fitness

But: planifier des seances, suivre des stats, et projeter les seances dans le calendrier.

Backend:

- `app/api/fitness.py`
- `app/services/fitness.py`
- `app/services/calendar_hub.py`

Frontend:

- `web/src/pages/FitnessPage.tsx`

Tests:

- `tests/test_fitness.py`
- `tests/test_calendar_overlap.py`

Invariants critiques:

- une seance ne doit pas chevaucher une tache, un repas, un abonnement, ou un event
- les exercices peuvent etre suivis en `reps` ou `duration`
- les seances projetees dans le calendrier viennent de la source `fitness_session`

### Finances / patrimoine

But: finances mensuelles, budgets, abonnements, patrimoine net, comptes et objectifs d'epargne.

Backend:

- `app/api/finances.py`
- `app/api/subscriptions.py`
- `app/api/patrimony.py`
- `app/services/life.py`

Frontend:

- `web/src/pages/FinancesPage.tsx`
- `web/src/store/financeStore.ts`
- `web/src/store/patrimonyStore.ts`

Invariants critiques:

- les budgets et syntheses mensuelles doivent rester alignes sur les transactions
- le patrimoine expose comptes + objectifs
- les abonnements ont aussi un impact calendrier via les projections dues

### REST seulement ou UI partielle

Ces domaines sont deja exposes en backend, mais la couverture UI reste partielle ou absente:

- `habits`
- `goals`
- `events`
- `subscriptions` (partiellement visible dans finances)
- `notes`
- `auth`

Pour toute extension UI sur ces domaines:

1. ajouter/etendre le store front
2. ajouter la page ou integrer dans une page existante
3. si l'assistant doit l'utiliser, verifier aussi `app/skill/actions.py` + `adamhub-assistant/`

## 4. Invariants transverses a ne pas casser

### Temps / timezone

- le backend travaille en UTC
- le front doit parser/serialiser sans decalage implicite du navigateur
- les DnD calendrier sont sensibles a cette contrainte

### Chevauchements calendrier

- la validation serveur est la source de verite
- le front essaye d'anticiper, mais le backend doit toujours refuser les conflits

### Produits magasin

- ne jamais fabriquer un `external_id`, un `store_label`, un `price_text` ou un `product_url`
- faire `supermarket.search` puis reutiliser le resultat selectionne

### Pantry sync

- un grocery checke peut creer/mettre a jour un pantry item
- une recette ou un repas ne retire du stock qu'au moment d'une confirmation explicite

### Pack assistant

- toute nouvelle capacite critique pour l'agent doit etre exposee dans `app/skill/actions.py`
- le pack doc (`adamhub-assistant/`) doit rester coherent avec le manifest
- les ids ne doivent jamais etre inventes

## 5. Comment modifier proprement le projet

### Ajouter un nouveau domaine metier

1. modeles: `app/models/entities.py`
2. schemas: `app/schemas/dto.py`
3. logique: `app/services/...`
4. routeur: `app/api/...`
5. agregation: `app/api/router.py`
6. tests backend
7. si UI: `web/src/store/` + `web/src/pages/`
8. si IA: `app/skill/actions.py` + `adamhub-assistant/`

### Ajouter une nouvelle enseigne supermarche

1. etendre `SupermarketStore`
2. enregistrer le provider dans `app/services/supermarket_registry.py`
3. implementer le scraper sous `app/services/scrapers/`
4. brancher `app/services/scraper_service.py`
5. tester normalisation + cache + mappings
6. verifier que le front ne hardcode pas Intermarche

### Changer la logique calendrier

Toucher ensemble:

- `app/services/calendar_hub.py`
- routeurs create/update des domaines planifiables
- `web/src/pages/CalendarPage.tsx`
- `tests/test_calendar_overlap.py`

### Changer le contrat recette / pantry / groceries

Toucher ensemble:

- `app/api/recipes.py`
- `app/api/meal_plans.py`
- `app/api/groceries.py`
- `app/api/pantry.py`
- `app/services/meal_planning.py`
- `app/services/grocery_pantry.py`
- `tests/test_grocery_pantry_flow.py`
- `tests/test_meal_plan_calendar_flow.py`

## 6. Commandes utiles

Backend tests:

```bash
.venv/bin/python -m pytest
```

Skill only:

```bash
.venv/bin/python -m pytest tests/test_skill.py
```

Frontend build:

```bash
cd web && npm run build
```

Compter routes REST + actions skill:

```bash
.venv/bin/python - <<'PY'
from app.main import app
from app.skill.actions import ACTION_CATALOG
print("api_routes", len([r for r in app.routes if getattr(r, "path", "").startswith("/api/v1")]))
print("skill_actions", len(ACTION_CATALOG))
PY
```

## 7. Ordre conseille avant un gros refactor

1. lire ce document
2. lire `docs/phase2_1_matrix.md`
3. verifier les tests du domaine cible
4. verifier si l'assistant depend du domaine
5. modifier backend avant frontend si le contrat change
6. finir par le skill et la doc
