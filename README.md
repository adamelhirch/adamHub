# AdamHUB

AdamHUB is a modular API-first app to manage daily life in one place:
- tasks and priorities
- personal finances and monthly summary
- grocery list
- recipes
- meal planning (breakfast/lunch/dinner) with pantry-gap auto grocery sync
- unified calendar hub (tasks, events, subscriptions, meals, manual entries)
- habits
- goals and milestones
- calendar events
- subscriptions / recurring bills
- pantry inventory
- notes and journal entries
- Linear projects/issues sync + issue creation

It also exposes a skill interface (`/api/v1/skill`) so an external AI agent like OpenClaw can interact with your data safely.

## Why this shape

- One backend to avoid app sprawl
- PostgreSQL-first setup for reliability and growth
- API key auth so both your app and AI agent can use the same API
- Skill execution endpoint for AI action orchestration

## Quick start

```bash
cp .env.example .env
docker compose up -d postgres
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

If PostgreSQL is running on another host, set `ADAMHUB_DB_URL` accordingly in `.env`.

Start the official frontend (`/web`) in dev:

```bash
cd web
npm install
npm run dev
```

Open:
- Frontend (official React/Vite): `http://localhost:5173/`
- Frontend legacy (FastAPI static): `http://localhost:8000/`
- App docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`
- Skill manifest: `http://localhost:8000/api/v1/skill/manifest`

Use header on all protected requests:
- `X-API-Key: <ADAMHUB_API_KEY>`
- quick auth test: `GET /api/v1/auth/check`

## API modules

- `tasks`: create, list, update status and priorities
- `finances`: add transactions and compute month summaries
- `groceries`: maintain a practical shopping list
- `groceries`: maintain shopping list; checked items automatically restock pantry
- `recipes`: store recipes and ingredient items
- `meal-plans`: assign recipes to breakfast/lunch/dinner, auto-add missing ingredients to groceries, then confirm-cooked to consume pantry (and unconfirm if needed)
- `calendar`: unified agenda + reminders + iCal export for iOS/Google/Notion Calendar subscription
- `habits`: define and log recurring habits
- `goals`: track long-term goals and milestones
- `events`: manage calendar events and upcoming agenda
- `subscriptions`: recurring bills and cost projections
- `pantry`: home inventory, low stock, expiring items
- `notes`: notes, journal entries, ideas, pinned notes
- `linear`: sync Linear projects/issues, read cache, create issue
- `skill`: discovery + action execution endpoint for OpenClaw

Current scope:
- 45+ REST endpoints under `/api/v1`
- 70+ AI actions available through `/api/v1/skill/execute`
- one API key-secured interface for app clients and OpenClaw

## Testing

Backend unit/integration suite:

```bash
.venv/bin/python -m pytest
```

Optional PostgreSQL smoke test (FK-sensitive paths):

```bash
export ADAMHUB_POSTGRES_SMOKE_URL='postgresql+psycopg://adamhub:adamhub@localhost:5432/adamhub'
.venv/bin/python -m pytest -m postgres
```

Frontend lint + unit tests:

```bash
cd web
npm run lint
npm run test
```

Playwright E2E checks are run against `http://localhost:5173` (frontend) and `http://localhost:8000` (API).

## Skill integration for OpenClaw

1. Configure your OpenClaw skill to call:
   - `GET /api/v1/skill/manifest` to discover actions
   - `POST /api/v1/skill/execute` to run actions
2. Inject these env vars in OpenClaw service:
   - `ADAMHUB_API_URL`
   - `ADAMHUB_API_KEY`
   - `ADAMHUB_LINEAR_API_TOKEN` (if using Linear actions)
   - `ADAMHUB_LINEAR_TEAM_ID` (optional default team for issue creation)
3. Keep both services on the same private Docker network in your VPS.

Calendar interoperability:
- `POST /api/v1/calendar/sync` to project tasks/events/subscriptions/meal-plans into one agenda
- `GET /api/v1/calendar/export.ics` to subscribe from iPhone Calendar, Google Calendar, or Notion Calendar

## Next ideas

Potential additions:
- contacts and relationship CRM
- travel planner with checklists
- workout and health metrics
- file vault for receipts and documents
- notification webhooks (email/telegram/discord)

## Deploy on same VPS

```bash
docker compose up -d --build
```

Then route through your reverse proxy (Caddy/Nginx/Traefik) with TLS.
