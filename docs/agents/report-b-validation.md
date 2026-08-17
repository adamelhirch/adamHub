# b4 — Validation de bout en bout du miroir panier Intermarché

Date : 2026-08-17 · Branche `adamelhirch/cart-b4-validation`

## Méthode

1. **Suite de tests** : `uv run pytest` → **280 passed, 1 skipped** (skip =
   postgres smoke, attendu), 0 failure/erreur.
2. **Smoke de bout en bout**, script reproductible
   `scripts/smoke_cart_mirror.py`, deux modes :
   - `--replay` (offline, **mode retenu pour la validation b4**) : rejoue une
     séquence figée de réponses canned dérivées des payloads réels capturés en
     session connectée (`tests/fixtures/intermarche/cart_response_*.json`,
     réduits de la HAR) via `httpx.MockTransport`. Aucun accès réseau.
   - `--cookies data/cookies_intermarche.json` (live) : chemin original contre
     le vrai `intermarche.com`.
3. Dans les deux modes, le script exerce **exactement le chemin backend
   réel** : `IntermarcheCartClient` (adapter b1) puis
   `cart_mirror._commit_state` (b2, la même fonction appelée par les
   endpoints `/supermarket/carts*`), qui réécrit le `SupermarketCart` local à
   partir de la réponse du site. Chaque étape compare l'état "site" (parsé de
   la réponse adapter) à l'état "local" (lu en base après l'écriture du
   miroir).

## Blocage constaté : validation live impossible

La session cookies live (`data/cookies_intermarche.json`, export du
2026-08-17) est **morte** : toute requête vers l'API panier
(`POST /api/service/panier/v1/stores/{store}/carts`) renvoie une erreur
401/403/DataDome captée par l'adapter :

```
=== Smoke miroir panier Intermarché — mode: live — statut: error ===
ERREUR: IntermarcheCartAuthError: Intermarché rejected the current cart
session (401/403 or DataDome). Re-import the connection cookies from a
fresh browser session.
```

Ce n'est pas un bug de code (le même schéma de rejet que a3 sur Leclerc) :
l'adapter détecte correctement la session morte et refuse toute mutation
plutôt que d'écrire un état local incohérent (`_run_with_client` ne touche
jamais le miroir local avant que l'adapter n'ait réussi). La validation
live nécessite un **ré-export frais des cookies** depuis une session
Intermarché connectée dans un navigateur.

**Décision utilisateur au gate b4** : le smoke **offline `--replay`**
documenté ci-dessous (site vs local qui matchent à chaque étape, sur les
payloads réels capturés) est **accepté comme validation suffisante** pour ce
run — pas besoin de cookies frais ni de nouvelle tentative live.

## Résultat du smoke offline (`--replay`)

Séquence rejouée : `read → add → qty → rm → add → clear`, couvrant le flux
demandé par b4 (ajout, vérification site+local, modification de quantité,
suppression, ré-ajout, vidage complet).

```
uv run python scripts/smoke_cart_mirror.py --replay

=== Smoke miroir panier Intermarché — mode: replay (offline) — statut: ok ===

[read] match=True
  site  : {}
  local : {}

[add] match=True
  site  : {"37731": 1}
  local : {"37731": 1}

[qty] match=True
  site  : {"37731": 3}
  local : {"37731": 3}

[rm] match=True
  site  : {}
  local : {}

[add] match=True
  site  : {"37731": 1}
  local : {"37731": 1}

[clear] match=True
  site  : {}
  local : {}

Site vs local : OK
```

| Étape | Action | Site (adapter, canned) | Local (SupermarketCart, DB) | Match |
|---|---|---|---|---|
| 1 | `read` (état initial) | panier vide | panier vide | ✅ |
| 2 | `add` item `37731` (Parmigiano reggiano AOP) qty 1 | `{37731: 1}` | `{37731: 1}` | ✅ |
| 3 | `qty` → 3 | `{37731: 3}` | `{37731: 3}` | ✅ |
| 4 | `rm` (suppression) | vide | vide | ✅ |
| 5 | `add` (re-ajout) | `{37731: 1}` | `{37731: 1}` | ✅ |
| 6 | `clear` (vidage) | vide (204) | vide | ✅ |

Les réponses `read`/`add`/`rm`/nouveau `add` sont les payloads **réels**
capturés dans `tests/fixtures/intermarche/cart_response_{empty,1_item}.json`
(mêmes fixtures que `tests/test_intermarche_cart.py`). La réponse `qty` est
synthétique : dérivée du fixture `cart_response_1_item.json` réel avec
uniquement la quantité/le montant modifiés (aucun fixture disque ne capture
un changement de quantité sur une ligne existante) — la forme (`item.*`)
reste celle observée en HAR.

Au niveau HTTP, chaque étape envoie le protocole attendu (vérifié par
`tests/test_intermarche_cart.py`, ré-exercé ici en bout en bout via
`cart_mirror`) :
- `add` → événement `QUANTITY` delta `+1`.
- `qty` → un `get_or_read_cart()` (re-sync) puis un delta `+2` (3 − 1 courant).
- `rm` → un `get_or_read_cart()` puis un delta `-1`.
- `clear` → `DELETE /customers/{uuid}/carts?sellerId=ITM` → 204, miroir local
  vidé (`_commit_state(session, user_id, None)`).

## Contrat de sortie (b1/b2/b3)

- Le smoke passe par le **même code de production** que les endpoints HTTP
  (`app.services.cart_mirror.read_cart/add_item/update_item_quantity/
  remove_item/clear_cart` appellent exactement `_run_with_client` +
  `_commit_state`, ici exercés directement) — aucune divergence entre le
  chemin testé et le chemin réel.
- → Aucune retouche nécessaire côté b1 (adapter)/b2 (endpoints)/b3 (UI) :
  le contrat miroir site↔local est respecté à chaque étape du cycle de vie
  (ajout, quantité, suppression, vidage).

## Conclusion

- **Suite de tests** : verte (280 passed, 1 skipped attendu, 0 échec).
- **Smoke offline (`--replay`)** : 6/6 étapes du cycle de vie matchent
  site vs local — **validation acceptée** pour ce run.
- **Smoke live (`--cookies`)** : bloqué par une session Intermarché morte
  (401/403/DataDome), pas de bug identifié côté adapter — la ré-validation
  live nécessitera un export de cookies frais quand disponible.

## Artefacts
- `scripts/smoke_cart_mirror.py` — smoke reproductible, modes `--replay`
  (offline, utilisé ici) et `--cookies` (live, pour ré-validation future).
