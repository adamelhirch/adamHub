# AdamHUB Phase 2.1 - Matrice complete endpoint -> UI -> skill

Date d'audit: 2026-03-06

## Snapshot global

- Backend REST sous `/api/v1`: **77 endpoints**.
- Skill OpenClaw: **73 actions** (`/api/v1/skill/manifest`).
- Frontend officiel: `/web` (React/Vite), legacy `app/web` retire.
- Pages web actives:
  - `/` Dashboard
  - `/finances`
  - `/groceries`
  - `/calendar`
  - `/tasks`
  - `/recipes`

Legend:
- `Client`: methode exposee dans `web/src/api.ts`
- `UI`: page(s) qui utilisent effectivement la methode
- `Skill`: action OpenClaw correspondante
- `Gap`: trou de couverture actuel

## Matrice endpoint -> client -> page -> skill

### auth (1)

- `GET /api/v1/auth/check` -> Client `API.auth.check` -> UI `Dashboard` -> Skill `n/a` -> Gap: aucun.

### tasks (4)

- `POST /api/v1/tasks` -> `API.tasks.create` -> `Operations` -> `task.create` -> Gap: creation ok.
- `GET /api/v1/tasks` -> `API.tasks.list` -> `Operations` -> `task.list` -> Gap: aucun.
- `PATCH /api/v1/tasks/{task_id}` -> `API.tasks.update` -> UI `non cable` -> `task.update` -> Gap UI.
- `POST /api/v1/tasks/{task_id}/complete` -> `API.tasks.complete` -> `Operations` -> `task.complete` -> Gap: aucun.

### finances (6)

- `POST /api/v1/finances/transactions` -> `API.finances.addTransaction` -> UI `non cable` -> `finance.add_transaction` -> Gap UI.
- `GET /api/v1/finances/transactions` -> `API.finances.listTransactions` -> UI `non cable` -> `finance.list_transactions` -> Gap UI.
- `POST /api/v1/finances/budgets` -> `API.finances.createBudget` -> UI `non cable` -> `finance.create_budget` -> Gap UI.
- `GET /api/v1/finances/budgets` -> `API.finances.listBudgets` -> UI `non cable` -> `finance.list_budgets` -> Gap UI.
- `GET /api/v1/finances/summary` -> `API.finances.getSummary` -> `Dashboard`, `Finances` -> `finance.month_summary` -> Gap: aucun.
- `GET /api/v1/finances/analytics` (compat) -> Client `non expose` -> UI `non cable` -> Skill `n/a` -> Gap faible (legacy).

### groceries (4)

- `POST /api/v1/groceries` -> `API.groceries.createItem` -> UI `non cable` -> `grocery.add_item` -> Gap UI.
- `GET /api/v1/groceries` -> `API.groceries.listItems` -> `Pantry` -> `grocery.list_items` -> Gap: aucun.
- `PATCH /api/v1/groceries/{item_id}` -> `API.groceries.updateItem` -> `Pantry` (check) -> `grocery.update_item` / `grocery.check_item` -> Gap: edition partielle.
- `DELETE /api/v1/groceries/{item_id}` -> `API.groceries.deleteItem` -> UI `non cable` -> `grocery.delete_item` -> Gap UI.

### pantry (6)

- `POST /api/v1/pantry/items` -> `API.pantry.createItem` -> UI `non cable` -> `pantry.add_item` -> Gap UI.
- `GET /api/v1/pantry/items` -> `API.pantry.listItems` -> `Pantry` -> `pantry.list_items` -> Gap: aucun.
- `PATCH /api/v1/pantry/items/{item_id}` -> `API.pantry.updateItem` -> UI `non cable` -> `pantry.update_item` -> Gap UI.
- `POST /api/v1/pantry/items/{item_id}/consume` -> `API.pantry.consume` -> UI `non cable` -> `pantry.consume_item` -> Gap UI.
- `DELETE /api/v1/pantry/items/{item_id}` -> `API.pantry.deleteItem` -> UI `non cable` -> `pantry.delete_item` -> Gap UI.
- `GET /api/v1/pantry/overview` -> `API.pantry.getOverview` -> `Pantry` -> `pantry.overview` -> Gap: aucun.

### recipes (3)

- `POST /api/v1/recipes` -> `API.recipes.create` -> `Operations` -> `recipe.add` -> Gap: aucun.
- `GET /api/v1/recipes` -> `API.recipes.list` -> `Calendar`, `Operations` -> `recipe.list` -> Gap: aucun.
- `GET /api/v1/recipes/{recipe_id}` -> `API.recipes.get` -> UI `non cable` -> `recipe.get` -> Gap UI.

### meal-plans (8)

- `POST /api/v1/meal-plans` -> `API.mealPlans.create` -> `Calendar`, `Operations` -> `meal_plan.add` -> Gap: aucun.
- `GET /api/v1/meal-plans` -> `API.mealPlans.list` -> `Calendar`, `Operations` -> `meal_plan.list` -> Gap: aucun.
- `GET /api/v1/meal-plans/{meal_plan_id}` -> Client `non expose` -> UI `non cable` -> Skill `n/a` -> Gap client + skill.
- `PATCH /api/v1/meal-plans/{meal_plan_id}` -> `API.mealPlans.update` -> UI `non cable` -> `meal_plan.update` -> Gap UI.
- `POST /api/v1/meal-plans/{meal_plan_id}/sync-groceries` -> `API.mealPlans.syncGroceries` -> `Calendar`, `Operations` -> `meal_plan.sync_groceries` -> Gap: aucun.
- `POST /api/v1/meal-plans/{meal_plan_id}/confirm-cooked` -> `API.mealPlans.confirmCooked` -> `Calendar`, `Operations` -> `meal_plan.confirm_cooked` -> Gap: aucun.
- `POST /api/v1/meal-plans/{meal_plan_id}/unconfirm-cooked` -> `API.mealPlans.unconfirmCooked` -> `Calendar`, `Operations` -> `meal_plan.unconfirm_cooked` -> Gap: aucun.
- `DELETE /api/v1/meal-plans/{meal_plan_id}` -> `API.mealPlans.delete` -> `Operations` -> `meal_plan.delete` -> Gap: aucun.

### calendar (10)

- `POST /api/v1/calendar/items` -> `API.calendar.addItem` -> `Calendar` -> `calendar.add_item` -> Gap: aucun.
- `GET /api/v1/calendar/items` -> `API.calendar.listItems` -> `Calendar` -> `calendar.list_items` -> Gap: aucun.
- `GET /api/v1/calendar/agenda` -> `API.calendar.agenda` -> UI `non cable` -> `calendar.agenda` -> Gap UI.
- `GET /api/v1/calendar/items/{item_id}` -> Client `non expose` -> UI `non cable` -> Skill `n/a` -> Gap client/UI.
- `PATCH /api/v1/calendar/items/{item_id}` -> Client `non expose` -> UI `non cable` -> `calendar.update_item` -> Gap client/UI.
- `DELETE /api/v1/calendar/items/{item_id}` -> Client `non expose` -> UI `non cable` -> `calendar.delete_item` -> Gap client/UI.
- `POST /api/v1/calendar/sync` -> `API.calendar.sync` -> `Calendar` -> `calendar.sync` -> Gap: aucun.
- `GET /api/v1/calendar/reminders/due` -> `API.calendar.dueReminders` -> `Calendar` -> `calendar.due_reminders` -> Gap: aucun.
- `POST /api/v1/calendar/reminders/{item_id}/ack` -> `API.calendar.ackReminder` -> `Calendar` -> `calendar.ack_reminder` -> Gap: aucun.
- `GET /api/v1/calendar/export.ics` -> Client `non expose` -> UI `non cable` -> Skill `n/a` -> Gap UX (abonnement calendrier externe).

### habits (4)

- `POST /api/v1/habits` -> `API.habits.create` -> `Operations` -> `habit.create` -> Gap: aucun.
- `GET /api/v1/habits` -> `API.habits.list` -> `Operations` -> `habit.list` -> Gap: aucun.
- `POST /api/v1/habits/{habit_id}/logs` -> `API.habits.log` -> `Operations` -> `habit.log` -> Gap: aucun.
- `GET /api/v1/habits/{habit_id}/logs` -> `API.habits.listLogs` -> UI `non cable` -> `habit.list_logs` -> Gap UI.

Note coherence: `habit.set_active` existe dans le skill mais pas en endpoint REST dedie.

### goals (7)

- `POST /api/v1/goals` -> `API.goals.create` -> `Operations` -> `goal.create` -> Gap: aucun.
- `GET /api/v1/goals` -> `API.goals.list` -> `Operations` -> `goal.list` -> Gap: aucun.
- `GET /api/v1/goals/{goal_id}` -> Client `non expose` -> UI `non cable` -> `goal.get` -> Gap client/UI.
- `PATCH /api/v1/goals/{goal_id}` -> `API.goals.update` -> UI `non cable` -> `goal.update` -> Gap UI.
- `POST /api/v1/goals/{goal_id}/milestones` -> `API.goals.addMilestone` -> UI `non cable` -> `goal.add_milestone` -> Gap UI.
- `GET /api/v1/goals/{goal_id}/milestones` -> `API.goals.listMilestones` -> UI `non cable` -> `goal.list_milestones` -> Gap UI.
- `PATCH /api/v1/goals/{goal_id}/milestones/{milestone_id}` -> `API.goals.updateMilestone` -> UI `non cable` -> `goal.update_milestone` -> Gap UI.

### events (6)

- `POST /api/v1/events` -> `API.events.create` -> `Operations` -> `event.create` -> Gap: aucun.
- `GET /api/v1/events` -> `API.events.list` -> UI `non cable` -> `event.list` -> Gap UI.
- `GET /api/v1/events/upcoming` -> `API.events.upcoming` -> `Operations` -> `event.upcoming` -> Gap: aucun.
- `GET /api/v1/events/{event_id}` -> Client `non expose` -> UI `non cable` -> `event.get` -> Gap client/UI.
- `PATCH /api/v1/events/{event_id}` -> Client `non expose` -> UI `non cable` -> `event.update` -> Gap client/UI.
- `DELETE /api/v1/events/{event_id}` -> Client `non expose` -> UI `non cable` -> `event.delete` -> Gap client/UI.

### subscriptions (6)

- `POST /api/v1/subscriptions` -> `API.subscriptions.create` -> `Operations` -> `subscription.create` -> Gap: aucun.
- `GET /api/v1/subscriptions` -> `API.subscriptions.list` -> UI `non cable` -> `subscription.list` -> Gap UI.
- `GET /api/v1/subscriptions/upcoming` -> `API.subscriptions.upcoming` -> `Operations` -> `subscription.upcoming` -> Gap: aucun.
- `GET /api/v1/subscriptions/projection` -> `API.subscriptions.projection` -> UI `non cable` -> `subscription.projection` -> Gap UI.
- `GET /api/v1/subscriptions/{subscription_id}` -> Client `non expose` -> UI `non cable` -> `subscription.get` -> Gap client/UI.
- `PATCH /api/v1/subscriptions/{subscription_id}` -> Client `non expose` -> UI `non cable` -> `subscription.update` -> Gap client/UI.

### notes (6)

- `POST /api/v1/notes` -> `API.notes.create` -> `Operations` -> `note.create` -> Gap: aucun.
- `GET /api/v1/notes` -> `API.notes.list` -> `Operations` -> `note.list` -> Gap: aucun.
- `GET /api/v1/notes/journal` -> `API.notes.journal` -> UI `non cable` -> `note.journal` -> Gap UI.
- `GET /api/v1/notes/{note_id}` -> Client `non expose` -> UI `non cable` -> `note.get` -> Gap client/UI.
- `PATCH /api/v1/notes/{note_id}` -> `API.notes.update` -> UI `non cable` -> `note.update` -> Gap UI.
- `DELETE /api/v1/notes/{note_id}` -> `API.notes.delete` -> UI `non cable` -> `note.delete` -> Gap UI.

### linear (4)

- `GET /api/v1/linear/projects` -> `API.linear.projects` -> `Operations` -> `linear.projects` -> Gap: aucun.
- `GET /api/v1/linear/issues` -> `API.linear.issues` -> `Operations` -> `linear.issues` -> Gap: aucun.
- `POST /api/v1/linear/issues` -> `API.linear.createIssue` -> `Operations` -> `linear.issue_create` -> Gap: aucun.
- `POST /api/v1/linear/sync` -> `API.linear.sync` -> `Operations` -> `linear.sync` -> Gap: aucun.

### supermarket (7)

- `GET /api/v1/supermarket/stores` -> Client `inline api` -> UI `Recipes`, `Groceries` -> Skill `n/a` -> Gap faible.
- `POST /api/v1/supermarket/search` -> Client `groceryStore.searchIntermarche` / `inline api` -> UI `Recipes`, `Groceries` -> Skill `n/a` -> Gap: aucun pour v1.
- `GET /api/v1/supermarket/search` -> Client `groceryStore.getCachedProducts` -> UI `Groceries` -> Skill `n/a` -> Gap UX mineur.
- `PUT /api/v1/supermarket/mappings/recipe-ingredients/{id}` -> Client `inline api` -> UI `Recipes` -> Skill `n/a` -> Gap: aucun.
- `GET /api/v1/supermarket/mappings/recipe-ingredients/{id}` -> Client `inline api` -> UI `Recipes` -> Skill `n/a` -> Gap: aucun.
- `PUT /api/v1/supermarket/mappings/pantry-items/{id}` -> Client `groceryStore.savePantryMapping` -> UI `Groceries` -> Skill `n/a` -> Gap: aucun.
- `GET /api/v1/supermarket/mappings/pantry-items/{id}` -> Client `groceryStore.fetchPantryMapping` -> UI `Groceries` -> Skill `n/a` -> Gap: aucun.
- `DELETE /api/v1/supermarket/mappings/{id}` -> Client `groceryStore.deleteMapping` / `inline api` -> UI `Recipes`, `Groceries` -> Skill `n/a` -> Gap: aucun.

### skill (2)

- `GET /api/v1/skill/manifest` -> `API.skill.manifest` -> UI `non cable` -> `n/a` (catalog endpoint) -> Gap UX/debug.
- `POST /api/v1/skill/execute` -> `API.skill.execute` -> `Operations` -> `n/a` (executor endpoint) -> Gap: aucun.

## Fonctionnalites deja solides

- Pipeline repas <-> courses <-> pantry coherent (check groceries et confirm/unconfirm cooked).
- Calendrier unifie avec reminders + NTFY deep link.
- Skill OpenClaw riche et exploitable en prod (73 actions).
- Linear connecte (sync, lecture, creation issue).

## Tickets prets a implementer (priorises)

### P0 (impact direct sur usage quotidien)

1. `P0-01` Calendrier: ajouter edition/suppression item manuel + detail item (`GET/PATCH/DELETE /calendar/items/{id}`) dans `/calendar`.
2. `P0-02` Pantry click deep-link: parser `?item=` et surligner/scroller l'item dans `/pantry` (coherence NTFY).
3. `P0-03` Finances complete UI: transactions + budgets + projection dans `/finances` (CRUD principal, filtres mois/categorie).
4. `P0-04` Goals milestones UI: creation/edition/complete des milestones + progression goal.
5. `P0-05` Subscriptions UI complete: liste + projection + edition d'un abonnement.

### P1 (couverture fonctionnelle)

6. `P1-01` Notes UI complete: journal timeline, edition et suppression note.
7. `P1-02` Events UI complete: liste detail + update + delete.
8. `P1-03` Pantry/Groceries CRUD complet (create/edit/delete hors check rapide).
9. `P1-04` Recipes detail page (`GET /recipes/{id}`) + edition ingredients.
10. `P1-05` Exposer `calendar.export.ics` dans l'UI (copie URL abonnement).

### P2 (coherence API/skill + DX)

11. `P2-01` Ajouter endpoint REST `PATCH /api/v1/habits/{id}` pour aligner avec `habit.set_active` (au lieu skill-only).
12. `P2-02` Ajouter endpoint `GET /api/v1/meal-plans/{id}` dans le client front (`API.mealPlans.get`) + vue detail.
13. `P2-03` Ajouter une page "Skill Inspector" (manifest + tests action + payload templates).

### P3 (integrations externes)

14. `P3-01` Module Revolut sync (si tu veux le faire ici): connecteur transactions -> `finances/transactions` + scheduler nightly + idempotence.
15. `P3-02` Module Drive sync (placeholder interface vers ton autre repo, webhooks/queue).

## Note Revolut (decision produit)

- Faisable techniquement, mais la voie depend du type de compte:
  - Revolut Business API (plus simple si compte business),
  - Open Banking (plus contraint/reglemente).
- Recommendation: commencer par import CSV/QIF + webhook interne, puis brancher Revolut apres stabilisation du hub.
