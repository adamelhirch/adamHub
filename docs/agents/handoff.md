# Handoff — adamHub — 2026-08-17

## Summary

Run B (« Miroir panier réel Intermarché ») de AdamHUB : le panier Intermarché d'AdamHUB est
devenu le miroir du vrai panier intermarche.com. b1 (adapter), b2 (endpoints miroir) et b3
(onglet Panier web) sont livrés et mergés (PRs #169/#170/#171). b4 (validation de bout en bout)
est en cours dans la worktree `cart-b4-validation` : le worker a découvert que l'API panier
live répond **403 DataDome avec les cookies actuels** et documente un smoke offline
(replay .har) en attendant des cookies frais — pas de `worker_done` reçu à ce jour.

## Orca state

- **Cockpit (cette session)** : worktree `frigatebird · cockpit MVP`
  (`/Users/adamelhirch/orca/workspaces/AdamHUB/frigatebird`), branche `main`, HEAD
  `1fff00e29253` (merge PR #164). **Attention : `main` local en retard de 3 merges sur
  `origin/main`** (f5e1ad0 → #169, 0725acc → #170, 82cc0f2 → #171) — `git pull` à prévoir.
  Carte (comment) : encore l'ancien texte « Supermarchés sans login livrés… (#136/#137) ».
- **Worktree primaire** : `/Users/adamelhirch/Documents/Projets perso/AdamHUB`
  (`isMainWorktree: true`, HEAD `f3ed8d0e4360`) — contient `docs/agents/plan.md` (Run B,
  approuvé 2026-08-16) et `docs/agents/setup.md` (conventions en vigueur). 1 terminal idle.
- **Worktree worker b4** : `cart-b4-validation`
  (`/Users/adamelhirch/orca/workspaces/AdamHUB/cart-b4-validation`), branche
  `adamelhirch/cart-b4-validation`, HEAD `82cc0f2` (= merge b3, base à jour d'origin/main),
  liée à l'issue #168, PR none. Contenu non commité : `scripts/smoke_cart_mirror.py`
  (untracked, en cours de finalisation).
- **Terminaux live frigatebird** : `term_452c3285` (coordinateur, cette session),
  `term_0be48754` (zsh data dir), `term_9e23a511` (uvicorn backend :51017, routes
  /supermarket OK), `term_7a646a35` (vite :5174). Primaire : `term_2dbc7869` (idle).
- **Terminal worker b4** : `term_914d6be0` (worktree cart-b4-validation) — **running**,
  agent opencode « Worker · DeepSeek V4 Flash », dernier message : finalisation du mode
  `--replay` (offline `httpx.MockTransport` + réponses du .har) pour documenter
  « site matches local », puis rapport + commit + push + PR.
- Autres worktrees/terminaux listés : CandiGO-deploy (stitch-design-*, UI-shell kanban gelé)
  et repos test — **hors périmètre**, ne pas toucher.

## Coordination

- **Run actif** : `run_5a191501fd7c` — « Run B — Miroir panier réel Intermarché (pilote) »,
  coordonné par `term_452c3285` (cette console). Tâches :
  | task | spec | status | livrable |
  |---|---|---|---|
  | `task_de91cb16f4a4` b1: adapter panier Intermarché | completed (2026-08-16 22:15Z) | PR #169 **MERGE** (f5e1ad0) |
  | `task_12156b55672c` b2: endpoint miroir /supermarket/carts* | completed (23:02Z) | PR #170 **MERGE** (0725acc) |
  | `task_fe3236f4dd14` b3: web onglet Panier miroir | completed (23:19Z) | PR #171 **MERGE** (82cc0f2) |
  | `task_a263396b31ea` b4: validation bout en bout | **dispatched** | dispatch `ctx_5188db2b213f`, attendu : pytest vert + smoke documenté + rapport `docs/agents/report-b-validation.md` + PR |
- **Dispatch b4** : `ctx_5188db2b213f`, assigné `term_914d6be0`, dispatches 2026-08-16 23:27,
  `status: dispatched`, `failure_count: 0`, **pas de `worker_done` reçu**, aucun heartbeat.
- **Mail** : `check --unread` → **0 message non lu** (run_5a191501fd7c, deliveryId null).
- **Travaux antérieurs de la session** (suivi pris dans cette console) : run extension v0.3.0
  (`run_d436d5c9f44b`, PRs #146-#150), run paniers locaux (`run_c40f493fa350`, #154-#156),
  run fixes recherche (`run_dd0734655159`, #160-#162), run Leclerc (`run_fa9758afcf66`,
  #164, issue #163 fermée) — **tous terminés et mergés**, issues fermées.

## Plan

- `docs/agents/plan.md` (worktree primaire) : **approuvé 2026-08-16** — Run B, sections
  b1-b4 ; hors périmètre : miroirs des 3 autres enseignes, sélecteur magasin persisté,
  paniers app-saas.
- `docs/agents/setup.md` (worktree primaire) : conventions en vigueur — merge gate
  CI-green, squash-merge + suppression branche/worktree, TDD, tracker **github** (issues
  miroirs créées par /orca-tasks), agents worker permissifs installés (opencode + Claude
  Code), **workers opencode lancés avec `opencode-go/deepseek-v4-flash`** (choix
  utilisateur), backend tests `uv run --extra dev pytest`.
- Pattern de reprise de worker : si `worker-start --retry-of` refuse
  (`task_not_startable`), `task-update --status ready` puis `worker-start` direct.
  `terminal close` peut renvoyer `None` au 1er appel → re-exécuter.

## Decisions

- **Source de vérité = le site** : chaque action AdamHUB → POST/DELETE au vrai panier
  Intermarché → la réponse écrase le panier local (reflet, pas source indépendante).
- **customer_uuid PAS dans les cookies** : il arrive via le redirect OAuth `/loading?userId=` ;
  b1/b2 le passent explicitement par l'appelant (best-effort cookie + attente de la vraie
  valeur pour validation live). **store_id** via `extract_pdv_ref_from_cookies`
  (`itm_pdv` ref=11131, Super Ramonville Saint-Agne).
- **Events panier = deltas signés** (`quantity +n`, remove = `-1`) ; lecture = POST events
  vides + `lastSynchronizedCart` rejoué ; vider = `DELETE customers/{uuid}/carts`.
- **Échec d'action** (session morte / 4xx / DataDome) : rejet + message clair dans l'UI,
  local non modifié, invitation à resynchroniser les cookies dans l'extension.
- Web : badge « Synchro avec le site » + bouton Resynchroniser ; fix intercepteur 401
  (un 401 /supermarket ne redirige plus vers /login) ; les 3 autres enseignes gardent le
  mode local du Run 1.
- **Verrou DataDome récurrent** (Leclerc puis maintenant panier Intermarché live) :
  décision prise — run dédié « proxy résidentiel systématique » (`data/proxies.txt`, 1005
  IP) pour Leclerc/Carrefour, plus tard. Leclerc = cookies session + IP-binding (302 →
  `authentification.aspx` = session révoquée).

## In progress / next

1. **b4** (`task_a263396b31ea`, worktree `cart-b4-validation`, term `term_914d6be0`) :
   worker encore actif — il va livrer un smoke offline (replay .har via MockTransport),
   le rapport `docs/agents/report-b-validation.md` et un PR (~#172). À la réception de
   `worker_done` : vérifier CI 4 jobs, squash-merge, `worker-release`,
   `terminal close term_914d6be0`, `worktree rm cart-b4-validation`, ack delivery,
   fermer l'issue #168 **et les issues miroirs #165-#167** (b1-b3 mergés mais issues
   encore OPEN).
2. **Blocage live b4** : l'API panier Intermarché répond 403 DataDome avec les cookies
   actuels (session `itm_session 7d190132…` morte, novaParams exp 2026-06-10). Si b4
   conclut « live impossible sans cookies frais » → **decision gate vers l'utilisateur** :
   (a) accepter le replay offline + signalement, clôturer b4 ; ou (b) l'utilisateur
   ré-exporte des cookies frais (extension AdamHUB Connect) et b4 relance le smoke live.
3. **Rafraîchir le cockpit** : `git pull` dans `frigatebird` (main en retard de 3 merges),
   puis mettre à jour le commentaire de la carte frigatebird.
4. **Runs suivants planifiés** : (i) proxy résidentiel Leclerc/Carrefour
   (`data/proxies.txt`) ; (ii) Run 2 sélecteurs magasins (Intermarché + Leclerc + Carrefour
   obligatoires ; .har Carrefour à la demande, hors repo ; .har Intermarché + Leclerc déjà
   dans `/Users/adamelhirch/Downloads/`).

## Suggested skills

- `orca-resume` — reprise de ce projet en nouvelle session (charge ce document).
- `orca-orchestrate` — boucle coordonnée du run (check --wait, gate b4, merges).
- `orca-handoff` — prochain handoff en fin de session.
- `orca-plan` — grill des runs suivants (proxy / sélecteurs).