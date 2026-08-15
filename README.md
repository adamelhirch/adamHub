# AdamHUB

AdamHUB is a personal operations hub with:

- one FastAPI backend (`app/`)
- one React/Vite frontend (`web/`)
- one assistant skill surface (`/api/v1/skill/*` + `adamhub-assistant/`)

It is designed to keep daily planning, groceries, pantry, recipes, fitness, money, and AI orchestration in the same system.

## Snapshot

State audited on `2026-03-29`:

- `110` REST routes under `/api/v1`
- `99` skill actions exposed through `/api/v1/skill/execute`
- `6` shipped frontend pages in `web/src/pages`
- PostgreSQL-first persistence with SQLModel + Alembic

## Current product surface

Frontend pages already shipped:

- `Calendar`: unified timeline, drag and drop scheduling, overlap prevention, meals, fitness sessions, tasks, events, subscriptions, manual items
- `Tasks`: two-tab workspace with one-shot tasks plus a `Routine` tab for recurring habits
- `Finances`: month summary, budgets, transactions, subscriptions, patrimony overview
- `Groceries`: grocery list + pantry, store-backed items, Intermarche search/mapping, pantry restock from checked groceries
- `Recipes`: manual recipe authoring, ingredient-by-ingredient editing, meal planning, supermarket-backed ingredients, cooked confirmation
- `Fitness`: session planning, measurements, stats, calendar-aware scheduling

REST modules available even when the UI is partial or missing:

- `auth`
- `tasks`
- `finances`
- `groceries`
- `pantry`
- `recipes`
- `meal-plans`
- `calendar`
- `fitness`
- `patrimony`
- `habits`
- `goals`
- `events`
- `subscriptions`
- `notes`
- `supermarket`
- `video`
- `skill`

## Core cross-domain flows

- Grocery items can be generic or store-backed. Store-backed items should come from `supermarket.search`, not from fabricated metadata.
- Checking a grocery item can restock pantry through `app/services/grocery_pantry.py`.
- Recipes can contain custom ingredients and store-backed ingredients.
- Meal plans and direct `recipe.confirm_cooked` consume pantry only when the meal/recipe is actually confirmed as cooked.
- Calendar is the shared planning layer. Tasks, meals, subscriptions, events, fitness sessions, and manual items are validated against overlap rules.
- Calendar also supports public signed `ICS/webcal` feeds. External calendar apps subscribe to AdamHUB feeds directly; no Google OAuth is required.
- Video ingestion returns transcript + source metadata only. Recipe extraction logic is intentionally delegated to the assistant client.

## Repo map

- `app/api/`: FastAPI routers per domain
- `app/services/`: business rules and cross-domain orchestration
- `app/models/entities.py`: SQLModel tables and enums
- `app/schemas/`: public API and skill contracts (one module per domain, re-exported via the package `__init__`; `dto.py` is a backwards-compatible facade)
- `app/skill/actions.py`: skill manifest + execution backend
- `web/src/pages/`: main app screens
- `web/src/store/`: frontend domain stores
- `adamhub-assistant/`: assistant pack, references, and domain skills
- `tests/`: backend tests for domain flows and invariants
- `docs/`: project-level documentation for future modifications

## Local development

Backend:

```bash
cp .env.example .env
podman-compose up -d postgres
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

`docker-compose.yml` is Podman-compatible (standard Compose format, valid OCI images), so it runs with `podman-compose`. Only PostgreSQL is started for local dev — the app container image is not built until the MVP is complete.

Frontend:

```bash
cd web
npm install
npm run dev
```

Default URLs:

- frontend dev: `http://localhost:5173/`
- backend docs: `http://localhost:8000/docs`
- health: `http://localhost:8000/health`
- skill manifest: `http://localhost:8000/api/v1/skill/manifest`

Auth header for protected routes:

- `X-API-Key: <ADAMHUB_API_KEY>`

## Calendar subscriptions

AdamHUB can publish signed calendar feeds that external apps subscribe to:

- create feed: `POST /api/v1/calendar/feeds`
- list feeds: `GET /api/v1/calendar/feeds`
- delete feed: `DELETE /api/v1/calendar/feeds/{feed_id}`
- public ICS feed: `GET /calendar/feed/{token}.ics`

Example feed creation:

```bash
curl -X POST http://localhost:8000/api/v1/calendar/feeds \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: change-me' \
  -d '{
    "name": "AdamHUB Tasks + Meals",
    "sources": ["task", "meal_plan"],
    "include_completed": true
  }'
```

The response includes:

- `ics_url`: direct HTTPS subscription URL
- `webcal_url`: ready-to-paste `webcal://...` URL for Apple Calendar, Google Calendar import/subscription, Outlook, and similar apps

Production note:

- backend secret list: `ADAMHUB_API_KEYS`
- assistant client secret: `ADAMHUB_API_KEY`
- in practice, use the same secret value on both sides

## Supermarket connections

Supported stores (registry at `app/services/store_catalog.py`): **Intermarché**, **Carrefour**, **Leclerc**, **Auchan**.

The reliable path is cookies: the AdamHUB Connect browser extension (`extension/`) dumps the cookies of a browser session (with a Drive store selected, since prices are store-specific) and posts them to `POST /api/v1/supermarket/connections/import`. Each store's scraper then calls the store's JSON/HTML API with those cookies.

**Auchan does not require a logged-in account**: any valid session cookie is enough — the price is server-rendered in the search HTML once a store is selected via `POST /api/v1/supermarket/auchan/selected-store` (wired to `POST /journey/update`), and `GET /api/v1/supermarket/auchan/offering-contexts` lists the selectable stores for an address. Searching without a selected store returns a clear "sélectionnez un magasin" error.

### Matrice connexion (recherche avec prix)

Compilée depuis les validations live des workers T2-T5 (détails dans
`docs/supermarket-reverse-engineering.md`). Les flags de capacité sont exposés
par `GET /api/v1/supermarket/stores` (`supports_sort`, `supports_promotions`,
`requires_store_selection`, `requires_login`).

| Enseigne | Login requis | Magasin sélectionné requis | Tri | Promos | Statut |
| --- | --- | --- | --- | --- | --- |
| Intermarché | Non | Oui (`itm_pdv` cookie, prix magasin) | Oui (`sort`) | Oui (`isPromo`) | Live |
| Carrefour | Non | Oui (Drive dans la session cookies) | Oui (`sort`) | Oui (filtre client) | Live |
| Leclerc | Non | Oui (sous-domaine `fdN` Drive) | Oui (`tri`) | Non | À valider |
| Auchan | Non | Oui (`POST selected-store`) | Oui (`sort`) | Non | Live validé |

Aucune des quatre enseignes n'exige un compte connecté pour la recherche avec
prix ; toutes exigent un contexte magasin pour que le prix corresponde au
magasin.

Login/password is a **best-effort alternative per store**: `POST /api/v1/supermarket/connections/import` accepts an optional `credentials` object `{username, password}` which is encrypted at rest (same Fernet container as cookies) and only works where a programmatic login exists without captcha/2FA. It is not wired to any scraper yet — the Leclerc reverse-engineered endpoint in particular needs **live validation** against a real session before relying on it. The browser extension remains the reliable path.

## Testing

Backend:

```bash
.venv/bin/python -m pytest
```

Optional PostgreSQL smoke tests:

```bash
export ADAMHUB_POSTGRES_SMOKE_URL='postgresql+psycopg://adamhub:adamhub@localhost:5432/adamhub'
.venv/bin/python -m pytest -m postgres
```

Frontend build:

```bash
cd web
npm run build
```

## Modification rules

Before changing a domain, read:

- `docs/project-tour.md`
- `docs/phase2_1_matrix.md`
- `adamhub-assistant/SKILL.md` if the change should also be exposed to AI

Keep these invariants in mind:

- use UTC end-to-end for scheduling data
- do not bypass overlap validation for calendar-linked domains
- do not create fake store metadata; use supermarket search first
- pantry should only move because of explicit stock actions, checked groceries, or cooked recipes/meal plans
- if a backend capability becomes important to the assistant, update both `app/skill/actions.py` and `adamhub-assistant/`

## Documentation index

- [Project tour](docs/project-tour.md)
- [Coverage matrix](docs/phase2_1_matrix.md)
- [Assistant master skill](adamhub-assistant/SKILL.md)
- [Assistant env example](adamhub-assistant/.env.example)
- [Assistant action catalog](adamhub-assistant/references/action-catalog.md)
