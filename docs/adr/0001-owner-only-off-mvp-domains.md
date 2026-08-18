# ADR-0001: Off-MVP domains stay Owner-only until they are tenant-scoped

- Status: accepted
- Date: 2026-08-14
- Issue: [#59](https://github.com/adamelhirch/adamHub/issues/59)

## Context

The SaaS pivot scoped five MVP domains (recipes, meal-plans, groceries, pantry,
supermarket) to tenants: every record carries a `user_id`, requests resolve an
acting user via `CurrentOrOwnerUser` (a JWT -> that user, an `X-API-Key` -> the
Owner), and cross-tenant access is a 404.

The remaining domains (finances, calendar, tasks, habits, goals, notes, events,
subscriptions, patrimony, video, skill, calendar feeds) predate tenancy:
their tables have **no** `user_id`. They were only guarded by `require_api_key`,
which accepts a valid Bearer JWT too. The consequence: any registered SaaS user
could present their JWT and read or write the Owner's personal data in these
domains, because nothing scoped or rejected them.

## Decision

Routers for non-MVP domains are **Owner-only**. Requests are gated by a new
`require_owner_only` dependency (alongside `CurrentOrOwnerUser` in
`app/api/deps.py`):

- A valid shared `X-API-Key` (legacy personal frontend) resolves to the Owner
  (`ADAMHUB_OWNER_EMAIL`) and is accepted.
- A valid JWT Bearer token is accepted **only if** it belongs to
  `ADAMHUB_OWNER_EMAIL`; any other user's token is rejected.
- No credentials -> 401, exactly like `require_api_key`.

The rejected non-Owner JWT gets a plain **401 "Not authorized"** rather than a
403. This keeps the response consistent with the existing "unauthenticated"
bucket and leaks nothing: the caller already presented credentials, so the reply
tells them nothing about whether the route or the data exists. No 403 or 404 is
introduced on these routes.

The five MVP routers are **not** touched and keep `CurrentOrOwnerUser` (JWT ->
user, `X-API-Key` -> Owner). `/auth/*` (including `/auth/me`) is **not**
locked and stays available to any authenticated user.

When a domain gets tenant-scoped (a `user_id` column + scoping reads and writes),
it moves out of the Owner-only list and adopts `CurrentOrOwnerUser` — this ADR
is the default state, not a permanent restriction.

## Superseded for finances (2026-08-18)

`finances` (transactions + budgets) is now tenant-scoped (`user_id` on
`financetransaction` and `budget`, additive migration `q8f2a4c6e1d3`,
backfill via `scripts/backfill_owner_tenant.py`) and its router uses
`CurrentOrOwnerUser` per route instead of the router-level `owner_only_user`
gate. A non-Owner JWT now reaches `/finances` and sees only its own rows;
cross-tenant rows are invisible. This ADR still governs the other off-MVP
domains (tasks, events, habits, goals, notes, subscriptions, …).

## Superseded for goals (2026-08-18)

`goals` is now tenant-scoped (`user_id` on `goal`, additive migration
`q4e8e2f5a1d7`, backfill via `scripts/backfill_owner_tenant.py`) and its
router uses `CurrentOrOwnerUser` per route instead of the router-level
`owner_only_user` gate. Goal milestones inherit their owner through the
`goal_id` FK — every milestone route/handler resolves the parent goal and
requires ownership before touching the milestone. A non-Owner JWT now
reaches `/goals` and sees only its own goals; cross-tenant goals (and their
milestones) are 404. This ADR still governs the other off-MVP domains
(tasks, events, habits, notes, subscriptions, …).

## Superseded for fitness (2026-08-18)

`fitness` (sessions + measurements) is now tenant-scoped (`user_id` on
`fitnesssession` and `fitnessmeasurement`, additive migration
`r2e4f6a8c1d3`, backfill via `scripts/backfill_owner_tenant.py`) and its
router uses `CurrentOrOwnerUser` per route instead of the router-level
`owner_only_user` gate. Creates auto-assign `user_id`, lists and the
overview filter by it, and get/update/complete/delete routes 404 on another
user's rows (no existence leak). The `fitness.*` skill handlers are scoped
to the acting user the same way. A non-Owner JWT now reaches `/fitness` and
sees only its own sessions and measurements; cross-tenant rows are 404.
This ADR still governs the other off-MVP domains (tasks, events, habits,
notes, subscriptions, …).

## Superseded for subscriptions (2026-08-18)

`subscriptions` is now tenant-scoped (`user_id` on `subscription`, additive
migration `r5a7b9c1e3d2f`, backfill via
`scripts/backfill_owner_tenant.py`) and its router uses `CurrentOrOwnerUser`
per route instead of the router-level `owner_only_user` gate. Creates
auto-assign the acting user, lists/upcoming/projection filter by it, and
get/update resolve the subscription with an ownership check that 404s on
another user's rows (no existence leak). The `subscription.*` skill actions
are scoped the same way. A non-Owner JWT now reaches `/subscriptions` and
sees only its own subscriptions; cross-tenant subscriptions are 404. This
ADR still governs the other off-MVP domains (tasks, events, habits, notes, …).

## Superseded for events (2026-08-18)

`events` is now tenant-scoped (`user_id` on `calendarevent`, additive
migration `r5a8c1e4f7b2`, backfill via `scripts/backfill_owner_tenant.py`)
and its router uses `CurrentOrOwnerUser` per route instead of the
router-level `owner_only_user` gate. The `event.*` skill handlers scope the
same way. This scopes the `CalendarEvent` table only — the calendar domain's
`CalendarItem` (and `app/services/calendar_hub.py`) stays shared and
un-scoped. A non-Owner JWT now reaches `/events` and sees only its own
events; cross-tenant events are 404. This ADR still governs the other
off-MVP domains (tasks, habits, notes, …).

## Superseded for habits (2026-08-18)

`habits` is now tenant-scoped (`user_id` on `habit` and `habitlog`, additive
migration `r5a7c9e2b4d6f`, backfill via
`scripts/backfill_owner_tenant.py`) and its router uses `CurrentOrOwnerUser`
per route instead of the router-level `owner_only_user` gate. Habit logs carry
their own `user_id`; every log route/handler first resolves the parent habit
with an ownership check. A non-Owner JWT now reaches `/habits` and sees only
its own habits and logs; cross-tenant habits (and their logs) are 404. This
ADR still governs the other off-MVP domains (tasks, notes, subscriptions, …).

## Superseded for tasks (2026-08-18)

`tasks` is now tenant-scoped (`user_id` on `task`, additive migration
`r3e5g7i9k2m4`, backfill via `scripts/backfill_owner_tenant.py`) and its
router uses `CurrentOrOwnerUser` per route instead of the router-level
`owner_only_user` gate. Creates auto-assign `user_id`, lists filter by it,
and get/update/complete/delete routes 404 on another user's rows (no
existence leak). The skill `task.*` actions are scoped to the acting user.
Note: `app/services/calendar_hub.py` is intentionally untouched here — its
calendar projection and slot validation still scan all tasks and are scoped
to the acting user in a follow-up change that depends on this `user_id`. This
ADR still governs the other off-MVP domains (notes, subscriptions, …).

## Superseded for calendar (2026-08-18)

`calendar` is now tenant-scoped end to end. `user_id` was added to
`calendaritem` (additive migration `s2f4a6c8e1d3`, backfill via
`scripts/backfill_owner_tenant.py`) and the `/calendar` router uses
`CurrentOrOwnerUser` per route instead of the router-level `owner_only_user`
gate. Creates auto-assign the acting user, lists/agenda/reminders/export
filter by it, and get/update/delete/ack routes 404 on another user's rows (no
existence leak). `app/services/calendar_hub.py` is scoped too: every
cross-domain read (Task, CalendarEvent, Subscription, FitnessSession,
Habit/HabitLog, and MealPlan/MealPlanCookConfirmation — the last fixing a
cross-tenant meal-plan leak that existed here even though meal plans are
scoped elsewhere) filters by the acting user's `user_id`, slot validation
only checks the acting user's calendar, and `sync_generated_calendar_items`
stamps `user_id` from the source row. The `calendar.*` skill handlers scope
the same way. The public calendar feed stays Owner-only (feeds are created
behind the owner gate and expose the ADAMHUB_OWNER_EMAIL user's calendar via
their token). The background scheduler keeps a global `user_id=None` mode for
its system-wide sync/reminder pass. A non-Owner JWT now reaches `/calendar`
and sees only its own items; cross-tenant items are 404. This ADR still
governs the other off-MVP domains (notes, …).

## Superseded for calendar feeds (2026-08-18)

`calendar feeds` is now tenant-scoped: `user_id` on `calendarfeed` (additive
migration `t2b4d6f8a1c3`, backfill via `scripts/backfill_owner_tenant.py`) and
the private `/calendar/feeds` router uses `CurrentOrOwnerUser` per route
instead of the router-level `owner_only_user` gate. Creates auto-assign the
acting user, lists filter by it, and delete 404s on another user's feeds (no
existence leak). The public token-authenticated `.ics` route is unchanged in
shape but now resolves the feed's own `user_id`: a feed only ever exposes the
calendar items of the user who owns it, never another tenant's (and never "all
users"). Legacy pre-backfill feeds (`user_id = NULL`) keep working and resolve
to the `ADAMHUB_OWNER_EMAIL` user — the same tenant the backfill claims them
for. This supersedes the t11 note that "the public calendar feed stays
Owner-only": the feed's token now scopes to its owner tenant instead of always
to the Owner. A non-Owner JWT now reaches `/calendar/feeds` and sees only its
own feeds. This ADR still governs the other off-MVP domains (skill, …).

## Consequences

- A SaaS user can no longer reach the Owner's unscoped data; the Owner's own
  JWT and the legacy `X-API-Key` keep working.
- The gate is a single dependency per router, so removing it when a domain is
  scoped is a one-line change.
- `require_api_key` remains for `/auth/check` and as the supermarket router's
  outer guard (the MVP supermarket router scopes per-route via
  `CurrentOrOwnerUser` on top).
- Tests added: a non-Owner JWT gets 401 on `/finances` and `/tasks` while the
  Owner (via `X-API-Key`) still gets 200, and the same SaaS user still reaches
  its MVP routes and `/auth/me`.
