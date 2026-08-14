# AdamHUB Linear Skill

Use for Linear project tracking: sync the remote workspace into the local cache, browse projects and issues, and create issues.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `linear.projects`
- `linear.issues`
- `linear.issue_create`
- `linear.sync`
<!-- END GENERATED: action-list -->

## Workflow: sync -> browse -> create

1. `linear.sync` (optional `project_id`) — refresh projects and issues into the local cache from the Linear API.
2. `linear.projects` — list projects (optional `source=cache|live`, `limit`).
3. `linear.issues` — list issues (optional `project_id`, `source=cache|live`, `limit`).
4. `linear.issue_create` — create an issue with `title`, optional `description`, `project_id`, `team_id`, `priority` (`0..4`), `assignee_id`, `due_date` (`YYYY-MM-DD`).

## Decision rules

- Run `linear.sync` before browsing when the user expects fresh data; default to the local cache for reads.
- If a `project_id` is needed and not provided, call `linear.projects` first.
- `priority` is `0..4` (0 = urgent, 4 = lowest); keep the numeric range.
- Use `source=live` only when the user explicitly wants the current Linear state and accepts the latency.
- Confirm the title and target project before `linear.issue_create`; do not invent `team_id` or `assignee_id`.

## Safety

- Never fabricate `project_id`, `team_id`, or `assignee_id`; resolve them from `linear.projects` / `linear.issues`.
- `linear.issue_create` is a write into the user's real Linear workspace — require explicit intent before creating.
- Do not delete or update Linear entities; this skill only lists, syncs, and creates.

## Example

```json
{"action":"linear.issue_create","input":{"title":"Fix login redirect","project_id":"PRJ-7","priority":1,"due_date":"2026-08-20"}}
```
