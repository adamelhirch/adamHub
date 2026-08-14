## Agent skills

### Issue tracker

Issues live in GitHub Issues at github.com/adamelhirch/adamHub. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context — one `CONTEXT.md` + `docs/adr/` at the repo root (not yet created; skills create these lazily). See `docs/agents/domain.md`.

## Commands

- Backend tests: `uv run --extra dev pytest` — the `dev` extra pulls in pytest; `uv run pytest` alone fails. Expected ~90 passed / 1 skipped (skip = postgres smoke).
- Web: `cd web && npm run build` (lint: `npm run lint`).
- App SaaS: `cd app-saas && npm run typecheck && npm run lint`.
