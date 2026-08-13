# AdamHUB Groceries Skill

Use for shopping list, pantry-aware restocking, and store-backed grocery creation.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `supermarket.list_stores`
- `supermarket.list_connections`
- `supermarket.import_connection`
- `supermarket.activate_connection`
- `supermarket.delete_connection`
- `supermarket.search`
- `grocery.add_item`
- `grocery.list_items`
- `grocery.update_item`
- `grocery.check_item`
- `grocery.delete_item`
<!-- END GENERATED: action-list -->

## Decision rules

- If the user wants a store-backed product, run `supermarket.search` first.
- Reuse the selected search result fields when calling `grocery.add_item`.
- If there is no good store result, create a generic grocery item instead.
- Use `grocery.check_item` only when the purchase is actually done.
- Remember that checked groceries can sync into pantry.
- See pantry state with `pantry.overview` (owned by the pantry skill) before restocking decisions.

## Safety

- If `item_id` is unknown, run `grocery.list_items` first.
- Do not perform bulk checks implicitly.
- Do not invent `external_id`, `price_text`, `product_url`, or `image_url`.

## Example

```json
{"action":"grocery.update_item","input":{"item_id":4,"quantity":2,"unit":"kg","priority":1}}
```

