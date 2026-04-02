# AdamHUB Recipes Skill

Use for recipe storage, transcript-to-recipe drafting, and pantry-aware cooking flows.

## Actions

- `video.fetch`
- `recipe.add`
- `recipe.list`
- `recipe.get`
- `recipe.update`
- `recipe.confirm_cooked`
- `recipe.delete`
- `meal_plan.add`
- `meal_plan.confirm_cooked`
- `meal_plan.unconfirm_cooked`
- `supermarket.search`

## Decision rules

- Save a new manual recipe with `recipe.add`.
- Read full details with `recipe.get`.
- Edit an existing recipe with `recipe.update`.
- If transcript input is available, call `video.fetch` first, then structure the recipe yourself.
- If the user wants ingredients tied to a store product, call `supermarket.search` first.
- Use `meal_plan.add` for future cooking.
- Use `recipe.confirm_cooked` only when the recipe was actually cooked without a meal plan.
- Use `meal_plan.confirm_cooked` when the cooked recipe came from a planned slot.

## Data quality rules

- `name` and `instructions` are required on create.
- Steps and utensils should be stored as arrays.
- Ingredients should include `name`, `quantity`, and `unit` when known.
- Store-backed ingredients should reuse the metadata returned by `supermarket.search`.

## Example

```json
{"action":"recipe.get","input":{"recipe_id":2}}
```

