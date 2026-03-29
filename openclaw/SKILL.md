# AdamHUB Master Skill for OpenClaw

Use this as the primary skill when OpenClaw must manage a full personal-life system through AdamHUB API.

This file is intentionally complete and production-oriented.

## 1) Runtime contract

- API base URL: `http://adamhub-api:8000`
- Auth header on every protected request: `X-API-Key: <ADAMHUB_API_KEY>`
- Manifest endpoint: `GET /api/v1/skill/manifest`
- Unified action endpoint: `POST /api/v1/skill/execute`
- Health endpoint: `GET /health`

## 2) Core objective

Convert natural language goals into deterministic API actions while preserving:

- correctness (no fabricated ids or values)
- safety (confirm risky writes)
- traceability (echo what changed)
- compact user communication (short, clear, actionable)

## 3) Startup routine (mandatory)

At session start:

1. Call `GET /health` once.
2. Call `GET /api/v1/skill/manifest` once.
3. Cache `actions` and `input_schema` for the session.
4. If manifest fetch fails, report blocker and stop mutations.

## 4) Universal execution loop

For each user request:

1. Intent classify: `read`, `write`, `multi-step`, `unclear`.
2. If `unclear`, ask one minimal clarifying question.
3. Choose action(s) from manifest only.
4. Build payload with strict field mapping.
5. Validate required fields before request.
6. For risky writes, request confirmation.
7. Execute API call.
8. If error, recover (see section 10).
9. Return concise result with ids and key values.
10. For multi-step goals, suggest next step.

## 5) Risk policy

Treat these as risky writes requiring explicit user confirmation:

- finance transaction amount > 200 (or currency equivalent)
- habit deactivation (`habit.set_active` with `active=false`)
- bulk-like operations requested by user language ("close all", "check all")
- edits where target id is ambiguous

Never execute risky writes on implicit intent.

## 6) Action routing map

Use this map for intent-to-action selection.

- planning/global status -> `dashboard.overview`
- add/list/update/complete task -> `task.create|list|update|complete`
- log/list expenses or income -> `finance.add_transaction|list_transactions`
- budget setup/review -> `finance.create_budget|list_budgets`
- monthly money synthesis -> `finance.month_summary`
- shopping list operations -> `grocery.add_item|list_items|update_item|check_item|delete_item` (checked items auto-sync pantry)
- recipe knowledge base -> `recipe.add|list|get`
- meal planning + auto grocery from pantry gaps -> `meal_plan.add|list|update|delete|sync_groceries|confirm_cooked|unconfirm_cooked|log_cooked` (plan with `planned_at` datetime; planning does not consume pantry; `confirm_cooked` consumes pantry; `unconfirm_cooked` rolls it back; `log_cooked` records an unplanned cooked recipe)
- unified agenda + reminders -> `calendar.sync|list_items|agenda|due_reminders|ack_reminder|add_item|update_item|delete_item`
- habits setup/tracking -> `habit.create|list|set_active|log|list_logs`
- goals and milestones -> `goal.create|list|get|update|add_milestone|list_milestones|update_milestone`
- events and agenda -> `event.create|list|upcoming|get|update|delete`
- recurring bills -> `subscription.create|list|get|update|upcoming|projection`
- pantry inventory -> `pantry.add_item|list_items|update_item|consume_item|delete_item|overview`
- notes and journal -> `note.create|list|get|update|delete|journal`
- linear project management -> `linear.projects|issues|issue_create|sync`

Full details are in:
- `references/action-catalog.md`

## 7) Field and value normalization

Normalize user input before calls:

- boolean strings to bool (`"yes" -> true`, `"no" -> false`)
- integer-like ids to int
- amount to float with dot decimal
- month summary params:
  - `year`: 4 digits
  - `month`: 1..12
- budget month format: `YYYY-MM`
- datetime format: ISO 8601 UTC when possible (`YYYY-MM-DDTHH:MM:SSZ`)

If a required value is missing, ask for it instead of guessing.

## 8) ID resolution strategy

Never invent ids.

When id is missing:

- task id -> call `task.list`
- grocery item id -> call `grocery.list_items`
- recipe id -> call `recipe.list`
- habit id -> call `habit.list`
- goal id -> call `goal.list`
- event id -> call `event.list`
- subscription id -> call `subscription.list`
- pantry item id -> call `pantry.list_items`
- note id -> call `note.list`
- meal plan id -> call `meal_plan.list`
- linear project id -> call `linear.projects`
- calendar item id -> call `calendar.list_items` or `calendar.agenda`

Then present best candidate ids and ask user to pick.

## 9) Multi-domain playbooks

Use small deterministic chains for common requests:

- "organize my day"
  1. `dashboard.overview`
  2. `task.list` with `only_open=true`
  3. optional `task.create` or `task.update`

- "check this month money"
  1. `finance.month_summary`
  2. optional `finance.list_transactions`
  3. optional `finance.create_budget`

- "meal + shopping"
  1. `recipe.list`
  2. `meal_plan.add` with `auto_add_missing_ingredients=true`
  3. `meal_plan.sync_groceries` (if needed)
  4. `grocery.list_items`

- "linear weekly check"
  1. `linear.sync`
  2. `linear.projects`
  3. `linear.issues`
  4. optional `linear.issue_create`

- "daily executive agenda"
  1. `calendar.sync`
  2. `calendar.agenda`
  3. `calendar.due_reminders`
  4. optional `calendar.ack_reminder`

More variants are in:
- `references/playbooks.md`

## 10) Error handling and recovery

If API returns non-2xx:

1. Read `detail` exactly.
2. Detect class:
   - auth error -> check API key and header name
   - validation error -> fix payload types/fields
   - not found -> refresh list and resolve id
   - unknown action -> refetch manifest and retry action selection
3. Retry once after correction.
4. If still failing, report blocker with last payload.

Detailed matrix:
- `references/error-recovery.md`

## 11) User response format

After each successful mutation:

- include action name
- include primary id
- include 2-4 key fields
- include one optional next step

Example style:

- "Created task #12: Pay rent (priority: high, due: 2026-03-05). Want me to split it into subtasks?"

For read operations:

- summarize top signal first
- then short bullet list of items
- avoid dumping raw JSON unless user asks

## 12) Privacy and security constraints

- Never expose `ADAMHUB_API_KEY`.
- Never include secrets in chat output.
- Do not fabricate financial values.
- Do not infer recurring finance behavior unless explicitly requested.
- Do not execute destructive intent on ambiguous wording.

## 13) Full action list (quick index)

- `dashboard.overview`
- `task.create`
- `task.list`
- `task.update`
- `task.complete`
- `finance.add_transaction`
- `finance.list_transactions`
- `finance.create_budget`
- `finance.list_budgets`
- `finance.month_summary`
- `grocery.add_item`
- `grocery.list_items`
- `grocery.update_item`
- `grocery.check_item`
- `grocery.delete_item`
- `recipe.add`
- `recipe.list`
- `recipe.get`
- `meal_plan.add`
- `meal_plan.list`
- `meal_plan.update`
- `meal_plan.delete`
- `meal_plan.sync_groceries`
- `meal_plan.confirm_cooked`
- `meal_plan.unconfirm_cooked`
- `calendar.add_item`
- `calendar.list_items`
- `calendar.update_item`
- `calendar.delete_item`
- `calendar.agenda`
- `calendar.sync`
- `calendar.due_reminders`
- `calendar.ack_reminder`
- `habit.create`
- `habit.list`
- `habit.set_active`
- `habit.log`
- `habit.list_logs`
- `goal.create`
- `goal.list`
- `goal.get`
- `goal.update`
- `goal.add_milestone`
- `goal.list_milestones`
- `goal.update_milestone`
- `event.create`
- `event.list`
- `event.upcoming`
- `event.get`
- `event.update`
- `event.delete`
- `subscription.create`
- `subscription.list`
- `subscription.get`
- `subscription.update`
- `subscription.upcoming`
- `subscription.projection`
- `pantry.add_item`
- `pantry.list_items`
- `pantry.update_item`
- `pantry.consume_item`
- `pantry.delete_item`
- `pantry.overview`
- `note.create`
- `note.list`
- `note.get`
- `note.update`
- `note.delete`
- `note.journal`
- `linear.projects`
- `linear.issues`
- `linear.issue_create`
- `linear.sync`

## 14) Domain skills

Use these local references for domain-specific behavior:

- action catalog: `references/action-catalog.md`
- playbooks: `references/playbooks.md`
- error recovery: `references/error-recovery.md`
- HTTP examples: `references/http-examples.md`

## 15) HTTP templates

Manifest:

```http
GET /api/v1/skill/manifest
X-API-Key: <ADAMHUB_API_KEY>
```

Execute:

```http
POST /api/v1/skill/execute
X-API-Key: <ADAMHUB_API_KEY>
Content-Type: application/json

{
  "action": "task.create",
  "input": {
    "title": "Pay rent",
    "priority": "urgent"
  }
}
```

More examples:
- `references/http-examples.md`
