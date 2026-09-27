## Agent skills

### Issue tracker

Issues live in GitHub Issues at github.com/adamelhirch/adamHub. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context — one `CONTEXT.md` + `docs/adr/` at the repo root (not yet created; skills create these lazily). See `docs/agents/domain.md`.

## Commands

- Backend tests: `uv run --extra dev pytest` — Expected ~350 passed / 1 skipped (skip = postgres smoke).
- App SaaS: `cd app-saas && npm run typecheck && npm run lint`.
