# Quickstart & Validation Guide: Multi-Store Supermarket Carts

This guide outlines the end-to-end scenarios to validate multi-store cart synchronization and agent interactions.

---

## Prerequisites

1. Active Python environment with dev dependencies:
   ```bash
   source .venv/bin/activate
   # or uv run ...
   ```
2. Database initialized with migrations:
   ```bash
   uv run alembic upgrade head
   ```
3. Test session cookies or mock adapters configured for target stores:
   - `SupermarketConnection` active for `carrefour`, `leclerc`, `auchan`, and `intermarche`.

---

## Validation Scenario 1: Automated Unit & Contract Test Suite

Run the full backend test suite covering cart adapters, multi-store cart mirroring, and MCP endpoints:

```bash
uv run --extra dev pytest tests/test_supermarket_cart.py tests/test_supermarket_cart_mirror.py
```

**Expected Outcome**:
- All tests pass with zero errors.
- Mock retailer responses are reconciled into `SupermarketCart` records.
- Invalidation tests verify that remote failure preserves local cart without mutation.

---

## Validation Scenario 2: End-to-End REST API Verification

Execute a curl sequence against a running local backend (`http://localhost:8000`):

```bash
# 1. Search for a product to populate SupermarketSearchCache
curl -s -X POST "http://localhost:8000/api/v1/supermarket/search" \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{"store": "carrefour", "query": "lait"}' | jq '.[0].id'

# Suppose returned cache_id is 42

# 2. Add product to Carrefour cart
curl -s -X POST "http://localhost:8000/api/v1/supermarket/carts/carrefour/items" \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{"cache_id": 42, "quantity": 2}' | jq .

# 3. Read live Carrefour cart
curl -s -X GET "http://localhost:8000/api/v1/supermarket/carts/carrefour" \
  -H "X-API-Key: test-key" | jq .

# 4. Clear Carrefour cart
curl -s -X DELETE "http://localhost:8000/api/v1/supermarket/carts/carrefour" \
  -H "X-API-Key: test-key" | jq .
```

**Expected Outcome**:
- Item addition reflects remote retailer response, returning updated items and total price.
- Read endpoint fetches current mirrored state.
- Clear endpoint returns cart with 0 items.

---

## Validation Scenario 3: AI Agent MCP Cart Interaction

In an agent session equipped with AdamHUB MCP tools:

1. Request agent to inspect shopping baskets:
   > *"Show me my current carts across all supermarkets."*
   Agent invokes `supermarket.list_carts`.
2. Request agent to add an item:
   > *"Search for butter on Auchan and add 1 pack to my Auchan cart."*
   Agent invokes `supermarket.search` then `supermarket.add_cart_item`.
3. Verify agent receives structured confirmation of updated total.

---

## Validation Scenario 4: Web UI Verification

1. Start frontend development server:
   ```bash
   cd web && npm run dev
   ```
2. Navigate to `http://localhost:5173/groceries` and click the **Panier** (Cart) tab.
3. Switch between store tabs (**Intermarché**, **Carrefour**, **Leclerc**, **Auchan**).
4. Verify that each tab loads the corresponding store's cart with live status badge, items, quantities, and totals.
5. Increment/decrement a quantity and observe the UI updating after the mirror call succeeds.
