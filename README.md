# AdamHUB

AdamHUB is a personal operations hub with:

- one FastAPI backend (`app/`)
- one React/Vite frontend (`web/`)
- one OpenClaw-compatible skill surface (`/api/v1/skill/*` + `openclaw/`)

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
- `Tasks`: task capture, filtering, scheduling, completion
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
- `linear`
- `supermarket`
- `video`
- `skill`

## Core cross-domain flows

- Grocery items can be generic or store-backed. Store-backed items should come from `supermarket.search`, not from fabricated metadata.
- Checking a grocery item can restock pantry through `app/services/grocery_pantry.py`.
- Recipes can contain custom ingredients and store-backed ingredients.
- Meal plans and direct `recipe.confirm_cooked` consume pantry only when the meal/recipe is actually confirmed as cooked.
- Calendar is the shared planning layer. Tasks, meals, subscriptions, events, fitness sessions, and manual items are validated against overlap rules.
- Video ingestion returns transcript + source metadata only. Recipe extraction logic is intentionally delegated to OpenClaw.

## Repo map

- `app/api/`: FastAPI routers per domain
- `app/services/`: business rules and cross-domain orchestration
- `app/models/entities.py`: SQLModel tables and enums
- `app/schemas/dto.py`: public API and skill contracts
- `app/skill/actions.py`: skill manifest + execution backend
- `web/src/pages/`: main app screens
- `web/src/store/`: frontend domain stores
- `openclaw/`: OpenClaw master skill, references, and specialized skills
- `tests/`: backend tests for domain flows and invariants
- `docs/`: project-level documentation for future modifications

## Local development

Backend:

```bash
cp .env.example .env
docker compose up -d postgres
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

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
- `openclaw/SKILL.md` if the change should also be exposed to AI

Keep these invariants in mind:

- use UTC end-to-end for scheduling data
- do not bypass overlap validation for calendar-linked domains
- do not create fake store metadata; use supermarket search first
- pantry should only move because of explicit stock actions, checked groceries, or cooked recipes/meal plans
- if a backend capability becomes important to OpenClaw, update both `app/skill/actions.py` and `openclaw/`

## Documentation index

- [Project tour](docs/project-tour.md)
- [Coverage matrix](docs/phase2_1_matrix.md)
- [OpenClaw master skill](openclaw/SKILL.md)
- [OpenClaw action catalog](openclaw/references/action-catalog.md)

