# AdamHUB Uber Eats Skill

Use for Uber Eats grocery delivery: address setup, store selection, product search, cart, and pantry import after delivery.

## Actions

<!-- BEGIN GENERATED: action-list (source: app/skill/actions.py ACTION_CATALOG) -->
- `ubereats.list_addresses`
- `ubereats.geocode_address`
- `ubereats.save_address`
- `ubereats.activate_address`
- `ubereats.delete_address`
- `ubereats.list_stores`
- `ubereats.set_selected_store`
- `ubereats.get_selected_store`
- `ubereats.search_products`
- `ubereats.add_to_cart`
- `ubereats.list_carts`
- `ubereats.list_past_orders`
- `ubereats.import_order_to_pantry`
- `ubereats.import_third_party_order`
<!-- END GENERATED: action-list -->

## Workflow: ubereats_grocery

End-to-end flow (setup once, then daily use):

SETUP (once):

1. `ubereats.geocode_address` — resolve the user's free-text delivery address into picker candidates with `lat`/`lng`.
2. `ubereats.save_address` with `activate=true` — persists the address and refreshes the active store list.
3. `ubereats.list_stores` — grocery stores deliverable to the active address (filtered to known FR brands).
4. `ubereats.set_selected_store` — persist the chosen store; later search/cart calls target it.

DAILY USE:

1. `ubereats.search_products` with `query` (optional `sort_by=price_asc|price_desc`) — returns up to ~70 products with `cache_id`, `price_text`, `image_url`.
2. `ubereats.add_to_cart` with the `cache_id` (optional `quantity`) — pushes into the real Uber Eats cart and mirrors the item into the grocery list (deduplicated by `external_id`).

AFTER DELIVERY:

1. `ubereats.import_order_to_pantry` with the tracking URL or UUID — imports the delivered items into pantry (deduplicated by `external_id`, substitutions reflected silently).

## Decision rules

- Always confirm the delivery address before geocoding; never guess a home address.
- When the user gives a textual address, run `ubereats.geocode_address` first and let the user pick from the candidates before `ubereats.save_address`.
- Use `ubereats.activate_address` when the user switches the delivery location; call `ubereats.list_stores` afterwards because store availability depends on the active address.
- If `ubereats.search_products` returns no result, do not fabricate a product; suggest rephrasing the query or using `supermarket.search` for Intermarché/Carrefour.
- `ubereats.add_to_cart` requires a `cache_id` from a prior `ubereats.search_products` on the same selected store. Re-adding the same product increments the quantity.
- `ubereats.import_order_to_pantry` is for the user's own orders. If the UUID belongs to another account's order (third-party tracking link), the action fails with a clear message — do not force it.
- Confirm before deleting an address with `ubereats.delete_address`.

## Safety

- Do not fabricate `lat`/`lng`; take them from `ubereats.geocode_address` results.
- Never import a third-party order through `ubereats.import_order_to_pantry`. When the user says a friend ordered for them, ask for screenshots of the tracking page, read them yourself via your vision capability, then call `ubereats.import_third_party_order` with the extracted items.
- Do not silently consume or import pantry stock; the pantry skill owns `pantry.*`.
- If no Uber Eats cookies are configured, the actions fail with an auth error — stop and surface the blocker instead of retrying endlessly.

## Example

```json
{"action":"ubereats.add_to_cart","input":{"cache_id":4321,"quantity":2}}
```
