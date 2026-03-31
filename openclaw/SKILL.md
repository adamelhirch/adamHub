# AdamHUB Master Skill for OpenClaw

Use this as the primary skill when OpenClaw must manage AdamHUB as one coherent personal-life system.

The source of truth is always the live manifest returned by:

- `GET /api/v1/skill/manifest`

As of `2026-03-29`, the skill surface exposes `99` actions.

## 1) Runtime contract

- API base URL: `ADAMHUB_API_URL`
- Compatibility alias: `ADAMHUB_URL`
- Auth header on every protected request: `X-API-Key: <ADAMHUB_API_KEY>`
- Health endpoint: `GET /health`
- Manifest endpoint: `GET /api/v1/skill/manifest`
- Unified action endpoint: `POST /api/v1/skill/execute`
- Supermarket store registry: `supermarket.list_stores`
- Video transcript intake: `video.fetch`

Runtime URL rules:

- Resolve the base URL from `ADAMHUB_API_URL` first, then fall back to `ADAMHUB_URL` if needed.
- If OpenClaw is outside the AdamHUB Docker network, use the public AdamHUB URL in `ADAMHUB_API_URL`.
- If OpenClaw runs in the same Docker network, `ADAMHUB_API_URL=http://adamhub-api:8000` is valid.
- Never use `127.0.0.1` unless OpenClaw and AdamHUB run in the exact same container namespace.
- If either `ADAMHUB_API_URL` or `ADAMHUB_URL` is already present with `ADAMHUB_API_KEY`, do not ask the user which variables are needed. Test the service first.

## 2) Core objective

Turn natural language requests into deterministic AdamHUB actions while preserving:

- correctness
- safety
- traceability
- compact user communication

## 3) Startup routine

At session start:

1. Assume "adamhub" refers to this AdamHUB service when this skill is loaded.
2. Read `ADAMHUB_API_URL`, or fall back to `ADAMHUB_URL`.
3. Call `GET /health`.
4. Call `GET /api/v1/skill/manifest`.
5. Cache the `actions` list and each `input_schema`.
6. If the manifest fails, stop all write attempts.

## 4) Universal execution loop

For each request:

1. Classify intent as `read`, `write`, `multi-step`, or `unclear`.
2. Ask one short clarifying question only if a required field is missing or the target is ambiguous.
3. Never repeat the same clarifying question more than once. If the user repeats the same request unchanged, execute the safest viable interpretation.
4. Resolve ids from live data, never by guessing.
5. Select only actions that exist in the current manifest.
6. Validate the payload against the manifest schema and domain rules.
7. Ask for confirmation before risky writes.
8. Execute.
9. On failure, inspect `detail`, recover once, and retry once.
10. Return a concise result with ids and key fields.

## 5) Risk policy

Require explicit confirmation before:

- high-value finance writes
- destructive deletes (`recipe.delete`, `grocery.delete_item`, `pantry.delete_item`, `fitness.delete_session`, `patrimony.delete_account`, `patrimony.delete_goal`, etc.)
- habit deactivation
- any bulk-like request
- any ambiguous target resolution

Never perform destructive writes on implicit intent.

## 6) Action routing map

- global status -> `dashboard.overview`
- tasks -> `task.create|task.list|task.update|task.complete`
- finances -> `finance.add_transaction|finance.list_transactions|finance.create_budget|finance.list_budgets|finance.month_summary`
- patrimony -> `patrimony.overview|patrimony.list_accounts|patrimony.add_account|patrimony.update_account|patrimony.delete_account|patrimony.list_goals|patrimony.add_goal|patrimony.update_goal|patrimony.delete_goal`
- groceries -> `supermarket.list_stores|supermarket.search|grocery.add_item|grocery.list_items|grocery.update_item|grocery.check_item|grocery.delete_item`
- pantry -> `pantry.add_item|pantry.list_items|pantry.update_item|pantry.consume_item|pantry.delete_item|pantry.overview`
- recipes -> `recipe.add|recipe.list|recipe.get|recipe.update|recipe.confirm_cooked|recipe.delete`
- meal planning -> `meal_plan.add|meal_plan.list|meal_plan.update|meal_plan.delete|meal_plan.sync_groceries|meal_plan.confirm_cooked|meal_plan.unconfirm_cooked|meal_plan.log_cooked`
- calendar -> `calendar.add_item|calendar.list_items|calendar.update_item|calendar.delete_item|calendar.agenda|calendar.sync|calendar.due_reminders|calendar.ack_reminder`
- fitness -> `fitness.overview|fitness.list_sessions|fitness.create_session|fitness.update_session|fitness.complete_session|fitness.delete_session|fitness.list_measurements|fitness.add_measurement|fitness.update_measurement|fitness.delete_measurement`
- habits / routine -> `habit.create|habit.list|habit.set_active|habit.log|habit.list_logs`
- goals -> `goal.create|goal.list|goal.get|goal.update|goal.add_milestone|goal.list_milestones|goal.update_milestone`
- events -> `event.create|event.list|event.upcoming|event.get|event.update|event.delete`
- subscriptions -> `subscription.create|subscription.list|subscription.get|subscription.update|subscription.upcoming|subscription.projection`
- notes -> `note.create|note.list|note.get|note.update|note.delete|note.journal`
- video ingestion -> `video.fetch`

## 7) Domain rules you must respect

### Grocery and supermarket rules

- Do not fabricate store metadata.
- If the user wants a store-backed grocery or pantry item, run `supermarket.search` first.
- If no usable result exists, create a generic item instead of forcing a fake store match.

### Recipe and pantry rules

- `recipe.add` and `recipe.update` can store custom ingredients and store-backed ingredients.
- Planning a meal does not consume pantry.
- `meal_plan.confirm_cooked` and `recipe.confirm_cooked` do consume pantry.
- `meal_plan.unconfirm_cooked` restores previously consumed pantry stock.

### Calendar rules

- AdamHUB enforces non-overlap across tasks, meals, events, subscriptions, manual items, and fitness sessions.
- When a create/update fails with an overlap error, propose a new free slot rather than insisting on the same one.

### Fitness rules

- Sessions can contain exercises tracked by reps or by duration.
- Fitness sessions also participate in calendar conflict validation.

### Tasks and routine rules

- Use `task.*` only for one-time work.
- Use `habit.*` for recurring routines, rituals, and habits.
- Do not duplicate a recurring routine into normal tasks unless the user explicitly wants that downgrade.
- If the user asks for a task at a specific datetime or duration, stay in `task.create` or `task.update` with `due_at` and `estimated_minutes`.
- Do not use `calendar.add_item` as a substitute for a real task request.
- If the user asks for steps or a checklist, store them in `subtasks`.
- Keep `description` for freeform notes only.
- If the user says "recreate" and the only missing detail is the exact step content, ask once. If they repeat the same request unchanged, use a neutral numbered placeholder list rather than looping.

### Video rules

- `video.fetch` returns transcript + metadata only.
- OpenClaw is responsible for recipe extraction from the transcript.

## 8) Field normalization

Normalize before calling the API:

- booleans from user language to `true/false`
- ids to integers when the schema expects integers
- floats with dot decimal
- `YYYY-MM` for budgets
- `YYYY-MM-DD` for date-only values
- ISO 8601 UTC for datetimes whenever possible

If a required field is missing, ask instead of guessing.

## 9) ID resolution strategy

When the user does not provide an id:

- task id -> `task.list`
- grocery item id -> `grocery.list_items`
- pantry item id -> `pantry.list_items`
- recipe id -> `recipe.list`
- meal plan id -> `meal_plan.list`
- calendar item id -> `calendar.list_items` or `calendar.agenda`
- fitness session id -> `fitness.list_sessions`
- fitness measurement id -> `fitness.list_measurements`
- patrimony account id -> `patrimony.list_accounts`
- patrimony goal id -> `patrimony.list_goals`
- habit id -> `habit.list`
- goal id -> `goal.list`
- event id -> `event.list`
- subscription id -> `subscription.list`
- note id -> `note.list`

Never invent ids.

## 10) Playbook shortcuts

### Meal + shopping

1. `recipe.list`
2. `recipe.get` for the chosen recipe
3. `meal_plan.add` with `auto_add_missing_ingredients=true` if the user wants it scheduled
4. Inspect missing ingredients
5. `supermarket.search`
6. Add groceries only from selected results or fall back to generic items

### Video to recipe

1. `video.fetch`
2. Infer recipe structure from transcript and description
3. `recipe.add` or `recipe.update`
4. If planning is requested, `meal_plan.add`
5. If shopping is requested, search the supermarket first

### Fitness week setup

1. `fitness.overview`
2. `fitness.list_sessions`
3. `calendar.list_items` or `calendar.agenda` if slot validation is needed
4. `fitness.create_session` for approved slots
5. `fitness.complete_session` only after the workout is actually done

### Patrimony review

1. `patrimony.overview`
2. `patrimony.list_accounts`
3. `patrimony.list_goals`
4. Optional updates with `patrimony.update_account` or `patrimony.update_goal`

### Daily agenda

1. `calendar.sync`
2. `calendar.agenda`
3. `calendar.due_reminders`
4. `task.list` with `only_open=true` if the user wants execution planning

More detail lives in `references/playbooks.md`.

## 11) Error handling

If the API returns non-2xx:

1. Read `detail` exactly.
2. Classify the failure:
   - auth error
   - validation error
   - missing id / target not found
   - overlap / business rule conflict
   - unknown action
3. Refresh the relevant list or manifest if needed.
4. Retry once with a corrected payload.
5. If it still fails, surface the blocker and stop.

Detailed recovery notes:

- `references/error-recovery.md`

## 12) Response style

After a successful write:

- mention the action
- mention the primary id
- mention 2 to 4 meaningful fields
- optionally suggest one next step

After a read:

- summarize the main signal first
- then list the most relevant items
- avoid raw JSON unless explicitly requested

## 13) Privacy and safety constraints

- Never expose `ADAMHUB_API_KEY`.
- Never print secrets.
- Never fabricate finance amounts.
- Never fabricate supermarket product metadata.
- Never silently consume pantry stock.
- Never bypass conflict rules by pretending a slot is free.

## 14) Quick action index

- `dashboard.overview`
- `task.create|task.list|task.update|task.complete`
- `finance.add_transaction|finance.list_transactions|finance.create_budget|finance.list_budgets|finance.month_summary`
- `fitness.overview|fitness.list_sessions|fitness.create_session|fitness.update_session|fitness.complete_session|fitness.delete_session|fitness.list_measurements|fitness.add_measurement|fitness.update_measurement|fitness.delete_measurement`
- `supermarket.list_stores|supermarket.search`
- `grocery.add_item|grocery.list_items|grocery.update_item|grocery.check_item|grocery.delete_item`
- `video.fetch`
- `recipe.add|recipe.list|recipe.get|recipe.update|recipe.confirm_cooked|recipe.delete`
- `meal_plan.add|meal_plan.list|meal_plan.update|meal_plan.delete|meal_plan.sync_groceries|meal_plan.confirm_cooked|meal_plan.unconfirm_cooked|meal_plan.log_cooked`
- `calendar.add_item|calendar.list_items|calendar.update_item|calendar.delete_item|calendar.agenda|calendar.sync|calendar.due_reminders|calendar.ack_reminder`
- `habit.create|habit.list|habit.set_active|habit.log|habit.list_logs`
- `goal.create|goal.list|goal.get|goal.update|goal.add_milestone|goal.list_milestones|goal.update_milestone`
- `event.create|event.list|event.upcoming|event.get|event.update|event.delete`
- `subscription.create|subscription.list|subscription.get|subscription.update|subscription.upcoming|subscription.projection`
- `patrimony.overview|patrimony.list_accounts|patrimony.add_account|patrimony.update_account|patrimony.delete_account|patrimony.list_goals|patrimony.add_goal|patrimony.update_goal|patrimony.delete_goal`
- `pantry.add_item|pantry.list_items|pantry.update_item|pantry.consume_item|pantry.delete_item|pantry.overview`
- `note.create|note.list|note.get|note.update|note.delete|note.journal`
