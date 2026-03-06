# AdamHUB Groceries Skill

Use for shopping list management.

## Actions

- `grocery.add_item`
- `grocery.list_items`
- `grocery.update_item`
- `grocery.check_item`

## Decision rules

- Add item request -> `grocery.add_item`
- Show list -> `grocery.list_items`
- Quantity/category/priority change -> `grocery.update_item`
- Mark bought/unbought -> `grocery.check_item`

## Safety

- If `item_id` unknown, run `grocery.list_items` first.
- Do not run implicit bulk checks.

## Example

```json
{"action":"grocery.update_item","input":{"item_id":4,"quantity":2,"unit":"kg","priority":1}}
```
