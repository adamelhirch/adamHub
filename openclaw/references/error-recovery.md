# AdamHUB Error Recovery

Use this matrix when `POST /api/v1/skill/execute` fails.

## Status 401 / Invalid API key

Symptoms:

- `detail: "Invalid API key"`

Actions:

1. Check header name exactly: `X-API-Key`.
2. Check runtime secret source.
3. Retry once.
4. If still failing, stop and report auth blocker.

## Status 400 / Validation or business error

Common details:

- `Unknown action: ...`
- `task_id not found`
- `item_id not found`
- `habit_id not found`
- `recipe_id not found`
- `goal_id not found`
- `milestone_id not found`
- `event_id not found`
- `subscription_id not found`
- `note_id not found`
- `month must be in format YYYY-MM`
- `No task fields to update`
- `No grocery fields to update`

Actions:

1. Read detail exactly.
2. Fix payload shape or values.
3. If id not found, refresh list action and resolve id with user.
4. Retry once.

## Status 422 / Request body schema mismatch

Symptoms:

- FastAPI validation errors, wrong field types

Actions:

1. Ensure root body is:

```json
{"action":"...","input":{}}
```

2. Convert fields to expected types.
3. Remove unknown fields.
4. Retry once.

## 5xx / server issue

Actions:

1. Retry once after short delay.
2. If persistent, report service issue and stop write operations.
3. Continue read operations only if they succeed.

## Fallback behavior rules

- Do not loop retries indefinitely.
- Do not mutate data while in unknown error state.
- Surface the final failing payload and endpoint for debugging.
