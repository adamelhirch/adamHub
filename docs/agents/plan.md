# Plan — adamHub — 2026-08-18

## Objective

Ouvrir aux utilisateurs SaaS les 11 domaines actuellement réservés au seul
Owner (tâches, finances, calendrier + flux calendrier, habitudes, objectifs,
événements, fitness, abonnements, patrimoine, notes, vidéo) : chaque table
gagne un `user_id`, chaque requête est scopée, chaque routeur passe de
`owner_only_user` à `CurrentOrOwnerUser` — exactement le motif déjà en place
pour les 5 domaines MVP (recettes/plannings/courses/garde-manger/
supermarché) et pour le nouveau serveur MCP (#178). `linear` est exclu :
retiré du projet entièrement (#181, scope creep hors périmètre).

Fait : au préalable, les données existantes appartiennent toutes à l'Owner
(usage mono-utilisateur historique) — chaque migration `user_id` backfill
les lignes existantes vers l'id Owner.

## Context

- `docs/adr/0001-owner-only-off-mvp-domains.md` — la frontière actuelle et
  pourquoi elle existe (les tables owner-only n'ont aucun `user_id`, un JWT
  SaaS pourrait sinon lire/écrire les données perso de l'Owner).
- Recherche menée avant ce plan (résumé ci-dessous, détail dans la
  conversation) : `app/services/calendar_hub.py` lit sans filtre `user_id`
  les tables `Task`, `CalendarEvent`, `Subscription`, `FitnessSession`,
  `Habit`/`HabitLog`, **et `MealPlan`/`MealPlanCookConfirmation` — pourtant
  déjà scopées MVP** pour générer l'agenda (`CalendarItem`). C'est un vrai
  bug de fuite cross-tenant déjà présent aujourd'hui sur `MealPlan`, pas
  seulement un risque futur — corrigé au passage par t11.
- `calendar_feeds` dérive entièrement de `calendar` (aucune donnée propre)
  et expose une route publique `.ics` non authentifiée par jeton — doit être
  scopée après `calendar`, avec une attention particulière sur ce jeton
  public.
- `app/skill/actions.py` : tous les handlers des 11 domaines reçoivent déjà
  `user_id` via `execute_action` (signature uniforme) mais ne l'utilisent
  jamais — le scoping s'ajoute dans les handlers existants, pas de nouveau
  branchement.
- `app/mcp/server.py` (`MVP_ACTION_PREFIXES`) est une deuxième porte,
  indépendante des routeurs REST, qui doit suivre chaque domaine ouvert.
- Décisions utilisateur (conversation) : ouvrir tout sauf linear (linear
  supprimé, #181) ; ajouter un topic ntfy par utilisateur ; la synchro
  calendrier téléphone (Apple/Google) est un chantier futur séparé, hors
  périmètre ici.

## Decisions

- Périmètre : les 11 domaines ci-dessus + le sujet notifications (topic
  ntfy par utilisateur). `linear` exclu (supprimé).
- Migration de données : chaque `user_id` ajouté est backfillé vers l'Owner
  pour les lignes existantes (pas de perte de données).
- Le cluster calendrier (tasks, events, subscriptions, fitness, habits,
  calendar, calendar_feeds) est coordonné : les 5 domaines "feuilles"
  d'abord (indépendants entre eux), puis `calendar` (qui les lit tous, y
  compris `meal_plan`), puis `calendar_feeds` (qui dérive de `calendar`).
- `app/mcp/server.py` + `adamhub-assistant/SKILL.md` (via
  `scripts/generate_skill_docs.py`) se mettent à jour en une seule passe
  finale, après que tous les domaines ont atterri — évite les conflits de
  fusion sur ce fichier partagé si chaque tâche le touchait séparément.
- ADR : `docs/adr/0001-...` est mis à jour en fin de chantier pour refléter
  le nouvel état (une fois qu'il n'y a plus de domaines "off-MVP" hors
  linear).
- Tracker/merge : github, CI-green + squash-merge (convention déjà en
  vigueur toute la session). Agent worker : opencode
  `opencode-go/deepseek-v4-flash` (convention déjà en vigueur).
- TDD par défaut sur chaque tâche : test de scoping cross-tenant (404 sur
  les données d'un autre utilisateur, motif déjà utilisé dans
  `tests/test_multi_tenant_scoping.py`) + test que l'Owner garde l'accès à
  ses données existantes après la migration de backfill.

## Out of scope

- `linear` (supprimé, #181).
- Synchronisation calendrier ↔ téléphone (Apple Calendar / Google Calendar) —
  chantier futur séparé, nécessite OAuth/CalDAV, pas juste du scoping DB.
- OAuth pour l'auth MCP (déjà noté hors périmètre dans #178).
- `calendar_feeds` : au-delà du scoping par `user_id` du propriétaire du
  flux, aucune autre évolution du format ICS.

## Tasks

### t1: finances — user_id sur FinanceTransaction + Budget
- spec: Ajouter `user_id` (migration + backfill Owner) sur `FinanceTransaction`
  et `Budget`. Scoper toutes les requêtes (`app/api/finances.py`,
  `app/skill/actions.py` handlers `finance.*`, `build_month_summary`).
  Remplacer `owner_only_user` par `CurrentOrOwnerUser` sur le routeur.
  TDD : test qu'un second utilisateur ne voit/modifie jamais les
  transactions/budgets d'un autre (404 cross-tenant, motif
  `test_multi_tenant_scoping.py`), test que l'Owner retrouve ses données
  existantes après backfill.
- blocked-by: none
- agent: worker (opencode-go/deepseek-v4-flash)
- isolated: yes

### t2: patrimony — user_id sur Account + SavingsGoal
- spec: Ajouter `user_id` (migration + backfill) sur `Account` et
  `SavingsGoal`. Scoper `app/api/patrimony.py` et les handlers
  `patrimony.*` — attention aux lookups auxiliaires `accounts_by_id` dans
  `_handle_patrimony_list_accounts/add_account/list_goals/add_goal/
  update_goal` qui font aujourd'hui un `select(Account)`/`select(SavingsGoal)`
  non scopé en plus de la requête principale. Router → `CurrentOrOwnerUser`.
  TDD : cross-tenant 404 + Owner backfill, comme t1.
- blocked-by: none
- agent: worker
- isolated: yes

### t3: notes — user_id sur Note
- spec: Ajouter `user_id` (migration + backfill) sur `Note`. Scoper
  `app/api/notes.py` et les handlers `note.*`. Router →
  `CurrentOrOwnerUser`. TDD : cross-tenant 404 + Owner backfill.
- blocked-by: none
- agent: worker
- isolated: yes

### t4: goals — user_id sur Goal + GoalMilestone
- spec: Ajouter `user_id` (migration + backfill) sur `Goal` (`GoalMilestone`
  reste scopé via son FK `goal_id`, pas de colonne propre nécessaire — à
  confirmer en implémentant). Scoper `app/api/goals.py` et les handlers
  `goal.*`. Router → `CurrentOrOwnerUser`. TDD : cross-tenant 404 + Owner
  backfill.
- blocked-by: none
- agent: worker
- isolated: yes

### t5: video — flip de dépendance uniquement
- spec: Pas de table (extraction stateless). Remplacer `owner_only_user`
  par `CurrentOrOwnerUser` sur `app/api/video.py`. TDD : un JWT non-Owner
  atteint désormais `video.fetch` avec succès (test qu'il n'est plus rejeté).
- blocked-by: none
- agent: worker
- isolated: yes

### t6: tasks — user_id sur Task
- spec: Ajouter `user_id` (migration + backfill) sur `Task`. Scoper
  `app/api/tasks.py` et les handlers `task.*`. Router →
  `CurrentOrOwnerUser`. **Ne pas toucher** `app/services/calendar_hub.py`
  ici (fait par t11, qui dépend de ce `user_id` existant). TDD :
  cross-tenant 404 + Owner backfill.
- blocked-by: none
- agent: worker
- isolated: yes

### t7: events — user_id sur CalendarEvent
- spec: Idem t6 pour `CalendarEvent` / `app/api/events.py` / handlers
  `event.*`. Ne pas toucher `calendar_hub.py`.
- blocked-by: none
- agent: worker
- isolated: yes

### t8: subscriptions — user_id sur Subscription
- spec: Idem t6 pour `Subscription` / `app/api/subscriptions.py` /
  handlers `subscription.*`. Ne pas toucher `calendar_hub.py`.
- blocked-by: none
- agent: worker
- isolated: yes

### t9: fitness — user_id sur FitnessSession + FitnessMeasurement
- spec: Idem t6 pour `FitnessSession`/`FitnessMeasurement` /
  `app/api/fitness.py` / handlers `fitness.*`. Ne pas toucher
  `calendar_hub.py`.
- blocked-by: none
- agent: worker
- isolated: yes

### t10: habits — user_id sur Habit + HabitLog
- spec: Idem t6 pour `Habit`/`HabitLog` / `app/api/habits.py` / handlers
  `habit.*`. Ne pas toucher `calendar_hub.py`.
- blocked-by: none
- agent: worker
- isolated: yes

### t11: calendar — CalendarItem + calendar_hub.py coordonné
- spec: Ajouter `user_id` (migration + backfill) sur `CalendarItem`. Scoper
  `app/api/calendar.py` et les handlers `calendar.*`. **Scoper aussi
  `app/services/calendar_hub.py`** : chaque lecture cross-domaine (`Task`,
  `CalendarEvent`, `Subscription`, `FitnessSession`, `Habit`/`HabitLog`,
  et **`MealPlan`/`MealPlanCookConfirmation`**) doit filtrer par le
  `user_id` de l'appelant — ce dernier point corrige une fuite cross-tenant
  déjà présente aujourd'hui sur les plannings repas (déjà scopés MVP par
  ailleurs, mais lus sans filtre ici). Router → `CurrentOrOwnerUser`. TDD :
  cross-tenant 404 sur `CalendarItem` direct + test que l'agenda généré
  (`calendar.sync`/`calendar.agenda`) d'un utilisateur ne contient jamais de
  tâche/événement/abonnement/séance/habitude/repas d'un autre utilisateur.
- blocked-by: t6, t7, t8, t9, t10
- agent: worker
- isolated: yes

### t12: calendar_feeds — scoping + jeton public
- spec: Ajouter `user_id` (propriétaire du flux) sur `CalendarFeed`,
  backfill Owner. Router privé → `CurrentOrOwnerUser`. Point sensible : la
  route publique `.ics` (non authentifiée, par jeton) doit continuer à
  fonctionner mais ne renvoyer que les `CalendarItem` du `user_id`
  propriétaire du flux, jamais tous les utilisateurs — vérifier
  `_collect_feed_items` en conséquence. TDD : cross-tenant 404 sur le
  routeur privé + test que le flux public d'un utilisateur n'expose jamais
  les items d'un autre utilisateur.
- blocked-by: t11
- agent: worker
- isolated: yes

### t13: notifications — topic ntfy par utilisateur
- spec: Ajouter un champ `ntfy_topic` (nullable) sur `User` (migration).
  Endpoints `GET`/`PUT /api/v1/auth/notifications` (ou équivalent) pour
  lire/définir son propre topic. `app/core/scheduler.py` route chaque
  rappel vers le topic de l'utilisateur propriétaire de l'item calendrier
  au lieu du topic global `ADAMHUB_NTFY_TOPIC` (qui reste le défaut pour un
  utilisateur sans topic configuré — dont l'Owner par défaut, migration à
  vérifier). UI : section dans `app-saas/src/app/(tabs)/account.tsx` (même
  écran que la clé API MCP) pour saisir son topic. TDD : deux utilisateurs
  avec deux topics différents, rappel généré pour chacun va au bon topic
  (mock de l'appel ntfy, pas d'appel réseau réel dans les tests).
- blocked-by: t11
- agent: worker
- isolated: yes

### t14: MCP + doc skill — synchronisation finale
- spec: Une fois t1-t13 mergées, ajouter à `MVP_ACTION_PREFIXES`
  (`app/mcp/server.py`) les préfixes des 11 domaines nouvellement scopés
  (`task`, `finance`, `calendar`, `habit`, `goal`, `event`, `fitness`,
  `subscription`, `patrimony`, `note`, `video`). Lancer
  `uv run python scripts/generate_skill_docs.py` pour resynchroniser
  `adamhub-assistant/SKILL.md` + `references/action-catalog.md`. Mettre à
  jour la description du frontmatter (n'est plus limité aux 5 domaines
  MVP). TDD : test MCP qu'un utilisateur non-Owner voit désormais
  `task.create`/`finance.add_transaction`/etc. dans `list_tools` et peut
  les exécuter (miroir des tests `test_mcp_server.py` déjà en place, à
  l'envers).
- blocked-by: t1, t2, t3, t4, t5, t6, t7, t8, t9, t10, t11, t12, t13
- agent: worker
- isolated: yes

### t15: ADR — documenter la fin de la frontière owner-only (hors linear)
- spec: Rédiger `docs/adr/0002-open-off-mvp-domains-to-saas-users.md`
  (statut accepted), qui référence et supersède `0001-...` pour tout sauf
  `linear` (déjà réglé par sa suppression, #181). Mettre à jour le statut
  de `0001-...` (superseded, avec renvoi vers 0002) sans réécrire son
  contenu historique. Mettre à jour `docs/project-tour.md` si la
  description des domaines y fait encore référence à une frontière
  owner-only.
- blocked-by: t14
- agent: worker
- isolated: yes

## Status
approved (2026-08-18)
