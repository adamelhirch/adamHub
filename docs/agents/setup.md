# Orca setup — adamHub — 2026-08-16

## Primary worktree
`AdamHUB` — `id:5b23e25d-e64f-49db-be0e-113430e9acf7::/Users/adamelhirch/Documents/Projets perso/AdamHUB` (`isMainWorktree: true`)

## Repo
`origin` → `https://github.com/adamelhirch/adamHub` (GitHub remote confirmed)

## Conventions
- CI-green merge gate: merge only PRs whose CI passes; never merge red.
- One branch = one PR = one responsibility; branch from `main`, delete branch + worktree after merge.
- TDD by default; tests run on every PR (GitHub Actions).
- Backend tests: `uv run --extra dev pytest` (~194 tests). Web: `cd web && npm run build`. App SaaS: `cd app-saas && npm run typecheck && npm run lint`.
- Tasks run in isolated task worktrees, never in the primary worktree.

## Issue tracker
**github** — via `gh` on `adamelhirch/adamHub`. `/orca-tasks` mirrors each task as a `gh issue` and links the task worktree (`orca worktree set --worktree <sel> --issue <num>`).

## Agents installed
- opencode: `~/.config/opencode/agents/worker.md` + `orchestrator.md`
- Claude Code: `~/.claude/agents/worker.md` + `orchestrator.md`
- Verified identical to `orca-setup` skill bundled definitions (2026-08-16).

## Guides
- `orca orchestration` — present in the binary (verified via `orca skills get orchestration`).
- `orca-cli` — present in the binary (verified via `orca skills get orca-cli`).

## Status
setup complete — 2026-08-16
