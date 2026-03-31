# AdamHUB HTTP Examples

All examples assume:

- `BASE_URL=$ADAMHUB_API_URL`
- `API_KEY=<ADAMHUB_API_KEY>`

Use:

- a public AdamHUB URL if OpenClaw is external
- `http://adamhub-api:8000` only if OpenClaw shares the same Docker network
- never `127.0.0.1` for a remote OpenClaw instance

## Health

```bash
curl -s "$BASE_URL/health"
```

## Manifest

```bash
curl -s -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/skill/manifest"
```

## Create task

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"task.create","input":{"title":"Pay rent","priority":"urgent"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Month summary

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"finance.month_summary","input":{"year":2026,"month":3}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Patrimony overview

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"patrimony.overview","input":{}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Add patrimony account

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"patrimony.add_account","input":{"name":"Livret A","account_type":"savings","balance":1200}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Fitness overview

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"fitness.overview","input":{}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Create fitness session

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "action":"fitness.create_session",
    "input":{
      "title":"Push session",
      "session_type":"strength",
      "planned_at":"2026-03-31T18:00:00Z",
      "duration_minutes":50,
      "exercises":[
        {"name":"Push-ups","mode":"reps","reps":20},
        {"name":"Plank","mode":"duration","duration_minutes":3}
      ]
    }
  }' \
  "$BASE_URL/api/v1/skill/execute"
```

## Add grocery item

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"grocery.add_item","input":{"name":"eggs","quantity":12,"unit":"item"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Search a supermarket product

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"supermarket.search","input":{"store":"intermarche","queries":["poulet"],"max_results":10}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Add a store-backed grocery item

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "action":"grocery.add_item",
    "input":{
      "name":"Aiguillettes de poulet",
      "quantity":1,
      "unit":"item",
      "category":"viande",
      "store_label":"Intermarche",
      "external_id":"123456",
      "packaging":"barquette de 270 g",
      "price_text":"3,89 EUR",
      "product_url":"https://www.intermarche.com/...",
      "image_url":"https://...",
      "note":"selected from supermarket search"
    }
  }' \
  "$BASE_URL/api/v1/skill/execute"
```

## Fetch a video source

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"video.fetch","input":{"url":"https://www.youtube.com/watch?v=example"}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Add recipe manually

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "action":"recipe.add",
    "input":{
      "name":"Pasta al limone",
      "description":"Simple citrus pasta",
      "instructions":"Cook pasta. Mix sauce. Combine.",
      "steps":["Boil the pasta","Prepare the sauce","Combine and serve"],
      "utensils":["pot","pan","spatula"],
      "prep_minutes":10,
      "cook_minutes":15,
      "servings":2,
      "tags":["pasta","quick"],
      "ingredients":[
        {"name":"pasta","quantity":200,"unit":"g"},
        {"name":"lemon","quantity":1,"unit":"item","store":"intermarche","store_label":"Intermarche","external_id":"lemon-001","category":"Fruits","packaging":"1 piece","price_text":"0,45 EUR"},
        {"name":"parmesan","quantity":40,"unit":"g"}
      ]
    }
  }' \
  "$BASE_URL/api/v1/skill/execute"
```

## Plan meal + auto groceries

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"meal_plan.add","input":{"planned_at":"2026-03-31T19:30:00Z","recipe_id":7,"auto_add_missing_ingredients":true}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Confirm cooked meal

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"meal_plan.confirm_cooked","input":{"meal_plan_id":42}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Pantry overview

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"pantry.overview","input":{"days":7}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Sync unified calendar

```bash
curl -s -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"action":"calendar.sync","input":{}}' \
  "$BASE_URL/api/v1/skill/execute"
```

## Export ICS

```bash
curl -s -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v1/calendar/export.ics" > adamhub-calendar.ics
```
