# AdamHUB Action Catalog

Authoritative reference for `POST /api/v1/skill/execute`.

Request shape:

```json
{
  "action": "<action_name>",
  "input": {}
}
```

<!-- BEGIN GENERATED: action-catalog (source: app/skill/actions.py ACTION_CATALOG) -->
## Supermarket and drive

- `supermarket.list_stores` — List supported supermarket stores and capabilities
  - `input_schema`: (none)

- `supermarket.list_connections` — List saved supermarket connections (cookie sets) across all stores. Each entry has an id, label, store, is_active flag and cookies_count.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan?

- `supermarket.import_connection` — Save a fresh cookie set for a supermarket. Set activate=true to make this connection the default consumer for the store.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan, `label`: string, `cookies`: object[]?, `credentials`: object?, `activate`: bool?, `connection_id`: int?

- `supermarket.activate_connection` — Switch the active connection for a store.
  - `input_schema`: `connection_id`: int

- `supermarket.delete_connection` — Delete a saved supermarket connection.
  - `input_schema`: `connection_id`: int

- `supermarket.list_offering_contexts` — List the Auchan stores selectable for an address.
  - `input_schema`: `zipcode`: string, `city`: string, `latitude`: float, `longitude`: float, `country`: string?

- `supermarket.select_auchan_store` — Select the Auchan store used for search.
  - `input_schema`: `seller_id`: string, `store_reference`: string, `store_label`: string, `channel`: string?, `location_label`: string?, `zipcode`: string?, `city`: string?, `country`: string?, `latitude`: float?, `longitude`: float?

- `supermarket.search` — Search a supermarket and cache the normalized results.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan?, `queries`: string[], `max_results`: int?, `promotions_only`: bool?

- `supermarket.get_cart` — Retrieve current contents and prices of a supermarket cart.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan, `force_sync`: bool?

- `supermarket.list_carts` — List all active supermarket shopping carts.
  - `input_schema`: (none)

- `supermarket.add_cart_item` — Add a product from search results to the store live cart.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan, `cache_id`: int, `quantity`: int?

- `supermarket.update_cart_item` — Update quantity of a line item in a store cart.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan, `item_id`: int, `quantity`: int

- `supermarket.remove_cart_item` — Remove a product line from a supermarket cart.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan, `item_id`: int

- `supermarket.clear_cart` — Empty the shopping cart for a specific retailer.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan

- `supermarket.search_stores` — Search physical supermarket drive stores by postal code or city across Leclerc, Carrefour, Intermarché, and Auchan.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan?, `zipcode`: string?, `city`: string?, `latitude`: float?, `longitude`: float?

- `supermarket.set_favorite_store` — Configure the user preferred drive store, pickup typology, and default optimization strategy.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan, `external_store_id`: string, `store_label`: string, `location_label`: string?, `pickup_type`: quai|spot|tape|pieton?, `optimization_strategy`: mdd|budget|bio?

- `supermarket.prepare_cart` — Generate a staging draft drive shopping cart resolving unchecked grocery items to real supermarket SKUs.
  - `input_schema`: `store`: intermarche|carrefour|leclerc|auchan?, `optimization_strategy`: mdd|budget|bio?, `external_store_id`: string?, `item_ids`: int[]?

- `supermarket.confirm_cart_sync` — Push the staging cart to the retailer drive cart, marking items as in_cart=True without restocking pantry.
  - `input_schema`: `job_id`: int

- `supermarket.confirm_pickup` — Confirm physical drive pickup of groceries: marks grocery items as checked=True and restocks pantry inventory.
  - `input_schema`: `job_id`: int

## Groceries

- `grocery.add_item` — Add an item to grocery list
  - `input_schema`: `name`: string, `quantity`: float?, `unit`: string?, `category`: string?, `image_url`: string?, `store_label`: string?, `external_id`: string?, `packaging`: string?, `price_text`: string?, `product_url`: string?, `priority`: int?, `note`: string?

- `grocery.list_items` — List grocery items
  - `input_schema`: `checked`: bool?, `limit`: int?

- `grocery.update_item` — Update a grocery item
  - `input_schema`: `item_id`: int, `quantity`: float?, `unit`: string?, `category`: string?, `checked`: bool?, `priority`: int?, `note`: string?

- `grocery.check_item` — Mark grocery item checked or unchecked
  - `input_schema`: `item_id`: int, `checked`: bool?

- `grocery.delete_item` — Delete a grocery item
  - `input_schema`: `item_id`: int

## Recipes

- `recipe.add` — Create a recipe with optional ingredients
  - `input_schema`: `name`: string, `description`: string?, `instructions`: string, `steps`: string[]?, `utensils`: string[]?, `prep_minutes`: int?, `cook_minutes`: int?, `servings`: int?, `tags`: string[]?, `source_url`: string?, `source_platform`: string?, `source_title`: string?, `source_description`: string?, `source_transcript`: string?, `ingredients`: [{name, quantity, unit, note, category, cache_id}]?

- `recipe.list` — List recipes
  - `input_schema`: `limit`: int?

- `recipe.get` — Get one recipe by id
  - `input_schema`: `recipe_id`: int

- `recipe.update` — Update a recipe
  - `input_schema`: `recipe_id`: int, `name`: string?, `description`: string?, `instructions`: string?, `steps`: string[]?, `utensils`: string[]?, `prep_minutes`: int?, `cook_minutes`: int?, `servings`: int?, `tags`: string[]?, `source_url`: string?, `source_platform`: string?, `source_title`: string?, `source_description`: string?, `source_transcript`: string?, `ingredients`: [{name, quantity, unit, note, category, cache_id}]?

- `recipe.confirm_cooked` — Confirm a recipe was cooked and consume pantry ingredients
  - `input_schema`: `recipe_id`: int, `servings_override`: int?, `note`: string?

- `recipe.unconfirm_cooked` — Undo a recipe-level cooked confirmation and restore pantry stock
  - `input_schema`: `recipe_id`: int

- `recipe.delete` — Delete a recipe and its dependent recipe ingredients / meal plans
  - `input_schema`: `recipe_id`: int

## Meal plans

- `meal_plan.add` — Plan a recipe at a specific datetime or slot
  - `input_schema`: `planned_at`: datetime?, `planned_for`: YYYY-MM-DD?, `slot`: breakfast|lunch|dinner?, `recipe_id`: int, `servings_override`: int?, `note`: string?, `auto_add_missing_ingredients`: bool?

- `meal_plan.log_cooked` — Log a recipe as cooked without pre-planning
  - `input_schema`: `recipe_id`: int, `cooked_at`: datetime?, `servings_override`: int?, `note`: string?

- `meal_plan.list` — List meal plans
  - `input_schema`: `date_from`: YYYY-MM-DD?, `date_to`: YYYY-MM-DD?, `slot`: breakfast|lunch|dinner?, `limit`: int?

- `meal_plan.update` — Update one meal plan
  - `input_schema`: `meal_plan_id`: int, `planned_at`: datetime?, `planned_for`: YYYY-MM-DD?, `slot`: breakfast|lunch|dinner?, `recipe_id`: int?, `servings_override`: int?, `note`: string?, `auto_add_missing_ingredients`: bool?

- `meal_plan.delete` — Delete one meal plan
  - `input_schema`: `meal_plan_id`: int

- `meal_plan.sync_groceries` — Sync missing ingredients to grocery list for one meal plan
  - `input_schema`: `meal_plan_id`: int

- `meal_plan.confirm_cooked` — Confirm meal was cooked and consume pantry ingredients
  - `input_schema`: `meal_plan_id`: int, `note`: string?

- `meal_plan.unconfirm_cooked` — Undo cooked confirmation and restore pantry
  - `input_schema`: `meal_plan_id`: int

## Pantry

- `pantry.add_item` — Add pantry item
  - `input_schema`: `name`: string, `quantity`: float?, `unit`: string?, `category`: string?, `min_quantity`: float?, `expires_at`: YYYY-MM-DD?, `location`: string?, `note`: string?

- `pantry.list_items` — List pantry items
  - `input_schema`: `low_stock_only`: bool?, `expiring_in_days`: int?, `limit`: int?

- `pantry.update_item` — Update pantry item
  - `input_schema`: `item_id`: int, `quantity`: float?, `unit`: string?, `category`: string?, `min_quantity`: float?, `expires_at`: YYYY-MM-DD?, `location`: string?, `note`: string?

- `pantry.consume_item` — Decrease pantry item quantity
  - `input_schema`: `item_id`: int, `amount`: float

- `pantry.delete_item` — Delete pantry item
  - `input_schema`: `item_id`: int

- `pantry.overview` — Get pantry overview
  - `input_schema`: `days`: int?

- `pantry.lookup_barcode` — Lookup product details by barcode via Open Food Facts
  - `input_schema`: `barcode`: string

<!-- END GENERATED: action-catalog -->

## Field highlights

- money datetimes: ISO 8601
- budget month: `YYYY-MM`
- date fields: `YYYY-MM-DD`
- enums are strict and case-sensitive
- update actions require an id plus at least one field to patch
- `supermarket.search` must be the source for store-backed grocery and pantry metadata
- `recipe.add` and `recipe.update` accept `steps`, `utensils`, source metadata, and store-backed ingredient fields
- `recipe.confirm_cooked` consumes pantry directly from a recipe
- `meal_plan.confirm_cooked` consumes pantry from a planned recipe
- `meal_plan.unconfirm_cooked` restores pantry stock
- `fitness.create_session` and `fitness.update_session` are subject to calendar overlap validation
- `patrimony.overview` returns net worth, active accounts, and savings goals
- `video.fetch` returns normalized metadata, transcript, and transcript segments; when captions are unavailable it can fall back to local Whisper
