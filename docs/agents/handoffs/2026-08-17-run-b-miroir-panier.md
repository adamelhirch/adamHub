# Handoff — adamHub — 2026-08-17

Snapshot du 2026-08-17 (session « frigatebird · cockpit MVP ») — voir
`docs/agents/handoff.md` (rolling) pour la version vivante.

## Summary

Run B (« Miroir panier réel Intermarché ») : b1 (adapter), b2 (endpoints miroir) et b3
(onglet Panier web) mergés (PRs #169/#170/#171). b4 (validation bout en bout) en cours dans
`cart-b4-validation` : l'API panier live répond 403 DataDome avec les cookies actuels, le
worker documente un smoke offline (replay .har) — pas de `worker_done` reçu.

## Orca state

- Cockpit : `frigatebird` (branche `main`, HEAD `1fff00e29253` — en retard de 3 merges sur
  origin/main, `git pull` à faire). Primaire : `/Users/adamelhirch/Documents/Projets perso/AdamHUB`
  (plan.md + setup.md). Worker b4 : `cart-b4-validation` (branche `adamelhirch/cart-b4-validation`,
  HEAD `82cc0f2`, issue #168, `scripts/smoke_cart_mirror.py` untracked).
- Terminaux frigatebird : `term_452c3285` (coordinateur), `term_0be48754`, `term_9e23a511`
  (uvicorn :51017), `term_7a646a35` (vite :5174). Worker b4 : `term_914d6be0` (running).
- Carte frigatebird : ancien commentaire (#136/#137) — à mettre à jour.

## Coordination

- Run `run_5a191501fd7c` ; tâches : b1/b2/b3 `completed` (merge #169/#170/#171),
  b4 (`task_a263396b31ea`) `dispatched` — dispatch `ctx_5188db2b213f`, assigné
  `term_914d6be0`, pas de worker_done, 0 mail non lu.
- Attendu b4 : pytest vert + smoke documenté + rapport
  `docs/agents/report-b-validation.md` + PR (~#172).

## Plan

- `docs/agents/plan.md` (primaire) : approuvé 2026-08-16, Run B, hors périmètre = miroirs
  des 3 autres enseignes, sélecteur magasin, paniers app-saas.
- `docs/agents/setup.md` (primaire) : merge gate CI-green, squash-merge, TDD, tracker
  github, workers opencode `opencode-go/deepseek-v4-flash` (choix utilisateur),
  tests `uv run --extra dev pytest`.

## Decisions

- Source de vérité = le site ; chaque action écrase le local ; customer_uuid via redirect
  OAuth (pas dans les cookies) ; store_id = itm_pdv ref (11131) ; events = deltas signés ;
  échec session → rejet + message UI, local intact ; badge « Synchro avec le site » ;
  fix intercepteur 401 ; DataDome récurrent → run dédié proxy résidentiel (proxies.txt,
  1005 IP) pour Leclerc/Carrefour (différé).

## In progress / next

1. b4 : attendre worker_done → vérifier CI, merge PR, worker-release, fermer terminal,
   `worktree rm cart-b4-validation`, ack, fermer issues #165-#168.
2. Blocage live : cookies Intermarché morts (403 DataDome) → decision gate utilisateur
   (accepter replay offline OU ré-exporter des cookies frais via l'extension et relancer).
3. `git pull` cockpit + mise à jour carte frigatebird.
4. Runs suivants : proxy résidentiel (Leclerc/Carrefour), Run 2 sélecteurs magasins.

## Suggested skills

- `orca-resume` (reprise), `orca-orchestrate` (boucle run b4), `orca-handoff` (fin de
  session), `orca-plan` (grill runs suivants).