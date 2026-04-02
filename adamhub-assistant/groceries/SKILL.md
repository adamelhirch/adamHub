# AdamHUB Groceries Skill

Use for shopping list, pantry-aware restocking, and store-backed grocery creation.

## Actions

- `supermarket.list_stores`
- `supermarket.search`
- `grocery.add_item`
- `grocery.list_items`
- `grocery.update_item`
- `grocery.check_item`
- `grocery.delete_item`
- `pantry.overview`

## Decision rules

- If the user wants a store-backed product, run `supermarket.search` first.
- Reuse the selected search result fields when calling `grocery.add_item`.
- If there is no good store result, create a generic grocery item instead.
- Use `grocery.check_item` only when the purchase is actually done.
- Remember that checked groceries can sync into pantry.

## Safety

- If `item_id` is unknown, run `grocery.list_items` first.
- Do not perform bulk checks implicitly.
- Do not invent `external_id`, `price_text`, `product_url`, or `image_url`.

## Example

```json
{"action":"grocery.update_item","input":{"item_id":4,"quantity":2,"unit":"kg","priority":1}}
```

