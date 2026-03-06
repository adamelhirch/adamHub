# AdamHUB Recipes Skill

Use for recipe storage and retrieval.

## Actions

- `recipe.add`
- `recipe.list`
- `recipe.get`

## Decision rules

- Save new recipe -> `recipe.add`
- Browse recipes -> `recipe.list`
- Need full details -> `recipe.get`

## Data quality rules

- `name` and `instructions` are required on create.
- Ingredients should include `name`, `quantity`, `unit` when available.
- If servings are omitted, default from API is accepted.

## Example

```json
{"action":"recipe.get","input":{"recipe_id":2}}
```
