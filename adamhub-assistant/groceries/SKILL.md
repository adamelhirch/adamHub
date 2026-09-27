# AdamHUB Groceries Skill

Use for shopping list, pantry-aware restocking, and store-backed grocery creation.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `supermarket.list_stores`
- `supermarket.list_connections`
- `supermarket.import_connection`
- `supermarket.activate_connection`
- `supermarket.delete_connection`
- `supermarket.list_offering_contexts`
- `supermarket.select_auchan_store`
- `supermarket.search`
- `supermarket.get_cart`
- `supermarket.list_carts`
- `supermarket.add_cart_item`
- `supermarket.update_cart_item`
- `supermarket.remove_cart_item`
- `supermarket.clear_cart`
- `supermarket.search_stores`
- `supermarket.set_favorite_store`
- `supermarket.prepare_cart`
- `supermarket.confirm_cart_sync`
- `supermarket.confirm_pickup`
- `grocery.add_item`
- `grocery.list_items`
- `grocery.update_item`
- `grocery.check_item`
- `grocery.delete_item`
<!-- END GENERATED: action-list -->

## Decision rules

- If the user wants a store-backed product, run `supermarket.search` first.
- Reuse the selected search result fields when calling `grocery.add_item` or `supermarket.add_cart_item`.
- If there is no good store result, create a generic grocery item instead.
- Use `supermarket.get_cart` to inspect the user's live basket for a store (`intermarche`, `carrefour`, `leclerc`, `auchan`), or `supermarket.list_carts` for an overview across all stores.
- To discover nearby drive pickup locations and save preferred drive stores with pickup typologies, use `supermarket.search_stores` and `supermarket.set_favorite_store`.
- To stage grocery items into a supermarket cart, run `supermarket.prepare_cart` (creates a `GroceryToCartJob`).
- To push staged items into the retailer basket, call `supermarket.confirm_cart_sync` (marks items `in_cart = True`, `checked = False`).
- Only call `supermarket.confirm_pickup` when the user has actually picked up their groceries: this sets `checked = True` and restocks the pantry (Principle III).
- To add a product to a retailer basket directly, search for it first to obtain its `external_id`, then call `supermarket.add_cart_item`.
- If a supermarket cart operation fails because no connection is active or cookies expired, guide the user to connect/refresh their account using the AdamHUB browser extension.
- Use `grocery.check_item` only when the purchase is actually done.
- Remember that checked groceries can sync into pantry.
- See pantry state with `pantry.overview` (owned by the pantry skill) before restocking decisions.

## Safety

- If `item_id` is unknown, run `grocery.list_items` first.
- Do not perform bulk checks implicitly.
- Do not invent `external_id`, `price_text`, `product_url`, or `image_url`.
- Cart mutations and syncs are always staged in `draft` status: agents must never attempt automated checkout or payment.

## Example

```json
{"action":"supermarket.add_cart_item","input":{"store":"carrefour","external_id":"3560070513567","name":"Lait demi-écrémé UHT 1L","quantity":2,"price":1.15}}
```

