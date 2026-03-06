# AdamHUB HTTP Examples

All examples assume:

- `BASE_URL=http://adamhub-api:8000`
- `API_KEY=<ADAMHUB_API_KEY>`

## Health

```bash
curl -s "$BASE_URL/health"
```

## Manifest

```bash
curl -s -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/skill/manifest"
```

## Auth check (frontend/iOS bootstrap)

```bash
curl -s -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/auth/check"
```

## Create task

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"task.create","input":{"title":"Pay rent","priority":"urgent"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Update task

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"task.update","input":{"task_id":12,"priority":"high"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Add expense

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"finance.add_transaction","input":{"kind":"expense","amount":39.9,"currency":"EUR","category":"food"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Month summary

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"finance.month_summary","input":{"year":2026,"month":3}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Add grocery item

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"grocery.add_item","input":{"name":"eggs","quantity":12,"unit":"item"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Create habit and log

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"habit.create","input":{"name":"Workout","frequency":"daily"}}' \
  "$BASE_URL/api/v1/skill/execute"

curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"habit.log","input":{"habit_id":3,"value":1,"note":"30 min"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Create goal

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"goal.create","input":{"title":"Run 10k","status":"active","progress_percent":10}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Create event

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"event.create","input":{"title":"Doctor","start_at":"2026-03-10T10:00:00Z","end_at":"2026-03-10T10:30:00Z","type":"health"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Subscription projection

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"subscription.projection","input":{"currency":"EUR"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Pantry overview

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"pantry.overview","input":{"days":7}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Plan meal + auto groceries

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"meal_plan.add","input":{"planned_for":"2026-03-06","slot":"dinner","recipe_id":7,"auto_add_missing_ingredients":true}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Confirm cooked meal (consume pantry now)

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"meal_plan.confirm_cooked","input":{"meal_plan_id":42}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Undo cooked confirmation (restore pantry)

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"meal_plan.unconfirm_cooked","input":{"meal_plan_id":42}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Sync unified calendar

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"calendar.sync","input":{}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Export ICS for iPhone/Google/Notion Calendar

```bash
curl -s -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/calendar/export.ics" > adamhub-calendar.ics
```
