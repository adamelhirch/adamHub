# AdamHUB Recipes Skill

Use for recipe storage, transcript-to-recipe drafting, and pantry-aware cooking flows.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `video.fetch`
- `recipe.add`
- `recipe.list`
- `recipe.get`
- `recipe.update`
- `recipe.confirm_cooked`
- `recipe.unconfirm_cooked`
- `recipe.delete`
- `meal_plan.add`
- `meal_plan.log_cooked`
- `meal_plan.list`
- `meal_plan.update`
- `meal_plan.delete`
- `meal_plan.sync_groceries`
- `meal_plan.confirm_cooked`
- `meal_plan.unconfirm_cooked`
<!-- END GENERATED: action-list -->

## Decision rules

- Save a new manual recipe with `recipe.add`.
- Read full details with `recipe.get`.
- Edit an existing recipe with `recipe.update`.
- If transcript input is available, call `video.fetch` first, then structure the recipe yourself.
- If the user wants ingredients tied to a store product, call `supermarket.search` first (owned by the groceries skill).
- Use `meal_plan.add` for future cooking. Dynamic meal duration is calculated from `prep_minutes + cook_minutes` (default 45 min) and checks for calendar timeline collisions.
- Use `recipe.confirm_cooked` only when the recipe was actually cooked without a meal plan. Pantry stock decrements down to 0 (no negative stock) and missing ingredients are reported.
- Use `recipe.unconfirm_cooked` to undo cooking and restore exact pantry quantities.
- Use `meal_plan.confirm_cooked` when the cooked recipe came from a planned slot.

## Data quality rules

- `name` and `instructions` are required on create.
- Steps and utensils should be stored as arrays.
- Ingredients should include `name`, `quantity`, and `unit` when known.
- Culinary disambiguation: `name` must be the singular base ingredient name specifying distinct culinary state when ambiguous (e.g. `Saumon frais` vs `Saumon fumé`, `Thon en boîte` vs `Thon frais`). Physical cuts and forms (e.g. `pavé`, `filet`, `émincé`, `gousse`) belong strictly in `note`.
- Physical measurability: Any ingredient that can be weighed or measured in mass/volume (meats, fish, liquids, pasta, grains, cheeses) MUST be expressed in standard metric units (`g`, `kg`, `ml`, `cl`, `l`). The unit `item` is strictly reserved for naturally countable, whole-piece items (e.g. `Avocat`, `Pomme`, `Oeuf`, `Citron`, `Oignon`). For fish and meat portions (e.g. salmon steaks), recipes MUST be specified in grams (e.g. 250 g), with piece counts or cuts recorded in notes (e.g. note: "2 pavés de 150 g").
- Standard units only (`g`, `kg`, `ml`, `cl`, `l`, `c. à soupe`, `c. à café`, `pincée`, `item`). Never use cuts or packaging as units (`pavés`, `morceaux`, `filets`, `tranches`, `boîtes`).
- One ingredient per line (never combine e.g. `Sel, poivre`).
- Store-backed ingredients should reuse the metadata returned by `supermarket.search`.

## Example

```json
{"action":"recipe.get","input":{"recipe_id":2}}
```

