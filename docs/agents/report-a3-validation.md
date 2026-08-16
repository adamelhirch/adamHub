# a3 — Validation globale des recherches (smoke 4 enseignes)

Date : 2026-08-16 · Branche `adamelhirch/fix-a3-validation` · PR #162

## Méthode

1. **Suite de tests** : `uv run --extra dev pytest` → **220 passed, 1 skipped** (skip = postgres smoke, attendu).
2. **Smoke live** via le chemin backend complet (`fetch_search_results` avec la
   connexion active DB, `user_id=1` — exactement ce que fait
   `POST /supermarket/search`), et en mode `--cookies-fs` (scrapers en direct
   avec le `data/` local). Script reproductible : `scripts/smoke_search_all.py`.

Requête testée : `lait`, `max_results=10`.

## Résultats par enseigne

| Enseigne | Nb résultats | Latence | Erreur |
|---|---|---|---|
| **intermarche** | 10 | 1.3–3.0 s | — |
| **carrefour** | 10 | 0.4–0.6 s | 403 Cloudflare **intermittent** sous rafale (rate-limit) ; OK après pause. Le fix a1 (curl_cffi impersonation) fonctionne. |
| **leclerc** | 0 | ~0.6 s | `LeclercAuthError` — **DataDome anti-bot** : la session cookies actuelle (export du 15/08) est rejetée. Le fix a2 (base URL `ADAMHUB_LECLERC_BASE_URL`) fonctionne : la requête atteint la bonne URL ; c'est la fraîcheur des cookies qui bloque. Même curl_cffi impersonation ne passe pas la challenge DataDome. |
| **auchan** | 10 | 1.0–1.6 s | — (sélection magasin DB Toulouse Pontjumeaux appliquée) |

### Détails échantillon (backend, query=lait)
- intermarche : `Grandlait frais - Lait frais de Montagne entier` — 1,61€
- carrefour : `Lait Demi-Ecrémé CARREFOUR CLASSIC'` — 1,05 € (1.05 € / L)
- auchan : `Lait demi-écrémé équitable UHT` — 7,62 €

## Contrat de sortie (fix a1/a2)

- a1 (carrefour) : change le client HTTP (curl_cffi impersonation), **parseurs et
  format de sortie inchangés** (testé par la suite carrefour, verte).
- a2 (leclerc) : change la résolution de la base URL (`ADAMHUB_LECLERC_BASE_URL`),
  **parser et format de sortie inchangés**.
- → **Aucune retouche de schémas/tests nécessaire** : `SupermarketSearchResult`
  et `normalize_search_result` couvrent déjà le contrat des 4 enseignes.

## Conclusion

- 3/4 enseignes répondent correctement de bout en bout (intermarche, carrefour,
  auchan) avec les cookies connectés.
- Leclerc : recherche **bloquée par DataDome** avec la session cookies actuelle —
  nécessite un **ré-export frais de `data/cookies_leclerc.json`** depuis un
  navigateur connecté (le message d'erreur du scraper le dit explicitement).
  Ce n'est pas un bug de code : le fix a2 a débloqué la config, le blocage est
  côté anti-bot + fraîcheur des cookies.
- CI : Backend (pytest), Web, App SaaS, Extension — **4/4 verts**.

## Artefacts
- `scripts/smoke_search_all.py` — smoke test reproductible (backend DB ou cookies-fs).
