# ADR-0002: Off-MVP domains are opened to SaaS users (tenant-scoped)

- Status: accepted
- Date: 2026-08-18
- Supersedes: [ADR-0001](0001-owner-only-off-mvp-domains.md) — Owner-only gate on off-MVP domains
- Issue: [#59](https://github.com/adamelhirch/adamHub/issues/59)

## Context

[ADR-0001](0001-owner-only-off-mvp-domains.md) locked every off-MVP domain
behind a router-level `require_owner_only` gate: only the Owner's JWT (or the
shared `X-API-Key`) could reach `finances`, `calendar`, `tasks`, `habits`,
`goals`, `events`, `fitness`, `subscriptions`, `patrimony`, `notes` and
`video`, because their tables had no `user_id` and nothing else would scope a
SaaS user's reads and writes to themself.

Since then, the multi-tenant pivot has tenant-scoped each of these domains one
at a time: every remaining domain now carries a `user_id` (additive migrations,
backfilled to the Owner via `scripts/backfill_owner_tenant.py`) and resolves
the acting user through `CurrentOrOwnerUser` in `app/api/deps.py` (JWT -> that
user, `X-API-Key` -> the Owner) exactly like the five MVP domains. The
route-level `owner_only_user` gate has been removed from every one of them.
ADR-0001 recorded each move as a "Superseded for …" section; those sections are
now complete, so the ADR-0001 boundary itself is gone.

`video` predates the pattern: its extraction endpoint is stateless (no table,
no user data — `app/services/video_intake.py` only fetches public pages), so
its router adopts `CurrentOrOwnerUser` without any `user_id` migration
([#182](https://github.com/adamelhirch/adamHub/pull/182)).

Linear is out of scope: the Linear integration was removed entirely in
[#181](https://github.com/adamelhirch/adamHub/pull/181) (feature creep from
another project), so there is no "linear" domain left to open — it is neither
owner-only nor tenant-scoped, it no longer exists.

## Decision

The owner-only boundary of ADR-0001 is **removed for all eleven off-MVP
domains**. They are tenant-scoped and served through `CurrentOrOwnerUser` per
route:

| Domain | Tables | Migration (alembic/versions/) | Scoped in |
|---|---|---|---|
| tasks | `task` | `r3e5g7i9k2m4_add_user_id_to_task.py` | t6 (#188) |
| finances | `financetransaction`, `budget` | `q8f2a4c6e1d3_add_user_id_to_finance_transaction_and_budget.py` | (#186) |
| calendar | `calendaritem` (+ `app/services/calendar_hub.py`) | `s2f4a6c8e1d3_add_user_id_to_calendaritem.py` | t11 (#192) |
| habits | `habit`, `habitlog` | `r5a7c9e2b4d6f_add_user_id_to_habit_and_habit_log.py` | t10 (#189) |
| goals | `goal` (milestones inherit via `goal_id`) | `q4e8e2f5a1d7_add_user_id_to_goal.py` | t4 (#185) |
| events | `calendarevent` | `r5a8c1e4f7b2_add_user_id_to_calendarevent.py` | t7 (#187) |
| fitness | `fitnesssession`, `fitnessmeasurement` | `r2e4f6a8c1d3_add_user_id_to_fitness_session_and_measurement.py` | t9 (#191) |
| subscriptions | `subscription` | `r5a7b9c1e3d2f_add_user_id_to_subscription.py` | t8 (#190) |
| patrimony | `account`, `savingsgoal` | `q1e2d3c4b5a6_add_user_id_to_account_and_savings_goal.py` | (#184) |
| notes | `note` | `q8g2d4f6a1c3_add_user_id_to_note.py` | t3 (#183) |
| video | — (stateless extraction) | none | #182 |

The private calendar-feed surface (`calendarfeed`, migration
`alembic/versions/t2b4d6f8a1c3_add_user_id_to_calendarfeed.py`, t12 #193/#194)
is tenant-scoped the same way — its public `.ics` route resolves the feed's own
`user_id` — and is covered by ADR-0001's calendar-feeds section, which this ADR
also supersedes.

Shared behavior, identical to the MVP domains:

- Creates auto-assign the acting user's `user_id`.
- Lists/filters scope by `user_id` (`CurrentOrOwnerUser`).
- get/update/delete resolve with an ownership check that 404s on another
  user's rows — no existence leak.
- Skill/MCP handlers scope the same way: `app/mcp/server.py` now admits the 16
  tenant-scoped prefixes (5 MVP + the 11 domains above) for any authenticated
  caller, and `MVP_ACTION_PREFIXES` documents that surface.
- Backfill of pre-tenancy rows: `scripts/backfill_owner_tenant.py` claims them
  for the Owner (`ADAMHUB_OWNER_EMAIL`).

Two surfaces deliberately **stay owner-only**:

- The HTTP skill router (`/api/v1/skill/manifest`, `/api/v1/skill/execute`)
  keeps its router-level `owner_only_user` gate; the assistant's execute
  surface remains Owner-only.
- The MCP action `dashboard.overview` (cross-domain personal aggregation) is
  not in the tenant-scoped prefix set and rejects non-Owner callers.

## Consequences

- Any authenticated SaaS user (JWT or per-user API key) reaches all eleven
  domains and sees only their own rows; the Owner's data is invisible to other
  tenants (404, not 403, on cross-tenant access).
- The Owner keeps full access through the same `CurrentOrOwnerUser` dependency;
  the shared `X-API-Key` still resolves to the Owner.
- ADR-0001 is superseded: its historical "Superseded for …" sections remain as
  the record of the incremental pivot, but the owner-only gate it established
  no longer applies to any of these domains.
- Remaining owner-only surface is now minimal and explicit: the skill router
  and `dashboard.overview` — see `app/api/skill.py` and
  `app/mcp/server.py` (`MVP_ACTION_PREFIXES`, `_action_allowed`).
- Tests: `tests/test_owner_only_routes.py` still asserts non-Owner JWTs get
  401 on the skill routes but 200 on tenant-scoped routers;
  `tests/test_multi_tenant_scoping.py` covers per-tenant isolation.