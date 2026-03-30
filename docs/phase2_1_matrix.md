# AdamHUB - Matrice backend / front / skill

Date d'audit: `2026-03-29`

Cette matrice remplace l'ancienne vue endpoint-par-endpoint devenue obsolète. Elle sert a voir rapidement quels domaines sont:

- exposes en REST
- cables dans le frontend officiel
- exposes a OpenClaw via le skill

## Snapshot

- REST FastAPI: `110` routes `/api/v1/*`
- Skill OpenClaw: `99` actions
- Frontend officiel: `6` pages principales

## Matrice par domaine

| Domaine | Prefix REST | Front officiel | Skill OpenClaw | Fichiers principaux | Notes |
| --- | --- | --- | --- | --- | --- |
| Auth | `/auth` | Non | Non | `app/api/auth.py` | Sert surtout a verifier la cle API |
| Tasks | `/tasks` | Oui | Oui | `app/api/tasks.py`, `web/src/pages/TasksPage.tsx`, `web/src/store/taskStore.ts` | Alimente aussi le calendrier |
| Finances | `/finances` | Oui | Oui | `app/api/finances.py`, `web/src/pages/FinancesPage.tsx`, `web/src/store/financeStore.ts` | Transactions + budgets + synthese |
| Patrimony | `/patrimony` | Oui | Oui | `app/api/patrimony.py`, `web/src/pages/FinancesPage.tsx`, `web/src/store/patrimonyStore.ts` | Comptes + objectifs d'epargne |
| Groceries | `/groceries` | Oui | Oui | `app/api/groceries.py`, `web/src/pages/GroceriesPage.tsx`, `web/src/store/groceryStore.ts` | Peut etre store-backed ou generique |
| Pantry | `/pantry` | Oui | Oui | `app/api/pantry.py`, `web/src/pages/GroceriesPage.tsx`, `web/src/store/groceryStore.ts` | Sync avec groceries et recettes |
| Supermarket | `/supermarket` | Oui | Oui | `app/api/endpoints/supermarket.py`, `app/services/scraper_service.py`, `app/services/supermarket_mapping.py` | v1: Intermarche uniquement |
| Recipes | `/recipes` | Oui | Oui | `app/api/recipes.py`, `web/src/pages/RecipesPage.tsx` | Creation manuelle cote front |
| Meal plans | `/meal-plans` | Oui | Oui | `app/api/meal_plans.py`, `app/services/meal_planning.py`, `web/src/pages/RecipesPage.tsx`, `web/src/pages/CalendarPage.tsx` | Planification + sync groceries + consommation pantry |
| Calendar | `/calendar` | Oui | Oui | `app/api/calendar.py`, `app/services/calendar_hub.py`, `web/src/pages/CalendarPage.tsx` | Timeline unifiee + anti-chevauchement |
| Fitness | `/fitness` | Oui | Oui | `app/api/fitness.py`, `app/services/fitness.py`, `web/src/pages/FitnessPage.tsx` | Seances + mesures + projection calendrier |
| Video | `/video` | Non | Oui | `app/api/video.py`, `app/services/video_intake.py` | Transcript seulement, pas de parsing recette cote backend |
| Habits | `/habits` | Non | Oui | `app/api/habits.py` | Backend et skill prets, UI absente |
| Goals | `/goals` | Non | Oui | `app/api/goals.py` | Backend et skill prets, UI absente |
| Events | `/events` | Non | Oui | `app/api/events.py` | Integres au calendrier |
| Subscriptions | `/subscriptions` | Partiel | Oui | `app/api/subscriptions.py`, `web/src/pages/FinancesPage.tsx` | Projection visible via finances, UI dediee absente |
| Notes | `/notes` | Non | Oui | `app/api/notes.py` | Backend et skill prets, UI absente |
| Skill | `/skill` | Non | n/a | `app/api/skill.py`, `app/skill/actions.py` | Surface AI unifiee |

## Pages front officielles

| Page | Domaine principal | Dependances backend |
| --- | --- | --- |
| `/` | Calendar | `calendar`, `tasks`, `meal-plans`, `events`, `subscriptions`, `fitness` |
| `/tasks` | Tasks | `tasks` |
| `/finances` | Finances + Patrimony | `finances`, `subscriptions`, `patrimony` |
| `/groceries` | Groceries + Pantry + Supermarket | `groceries`, `pantry`, `supermarket` |
| `/recipes` | Recipes + Meal plans + Supermarket | `recipes`, `meal-plans`, `supermarket` |
| `/fitness` | Fitness | `fitness` |

## Skill OpenClaw: couverture utile

### Bien couverts

- tasks
- finances
- patrimony
- groceries
- pantry
- supermarket search
- recipes
- meal plans
- calendar
- fitness
- habits
- goals
- events
- subscriptions
- notes
- video transcript intake

### Contraintes a rappeler cote IA

- pour un produit magasin, chercher d'abord puis reutiliser le resultat
- si aucun match magasin n'est valide, creer un item generique
- ne pas consommer le pantry tant qu'un repas ou une recette n'est pas explicitement confirme comme cuisine
- respecter les conflits du calendrier

## Tests de reference

| Test | Ce qu'il verrouille |
| --- | --- |
| `tests/test_skill.py` | Manifest skill + actions critiques |
| `tests/test_supermarket.py` | cache, mapping, recherche magasin |
| `tests/test_grocery_pantry_flow.py` | achats -> pantry |
| `tests/test_meal_plan_calendar_flow.py` | repas -> groceries -> pantry -> calendrier |
| `tests/test_calendar_overlap.py` | interdiction des chevauchements |
| `tests/test_fitness.py` | seances fitness + projection calendrier |
| `tests/test_video_intake.py` | transcript / metadata / whisper fallback |

## Chantiers probables ensuite

1. Completer l'UI pour les domaines REST-only ou partiels: habits, goals, events, notes, subscriptions.
2. Ajouter de nouvelles enseignes en reutilisant `supermarket_registry.py`.
3. Continuer la decoupe du frontend pour reduire la taille du bundle principal.
4. Ajouter des skill playbooks plus fins pour les flows courses / recettes / fitness / patrimoine.
