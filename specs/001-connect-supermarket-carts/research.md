# Research & Architectural Decisions: Connect Multi-Store Supermarket Carts

## 1. Multi-Store Cart Mirror Architecture

### Decision
Generalize the proven Intermarché cart mirror pattern into a unified multi-store mirror subsystem in `app/services/cart_mirror.py`, supported by store-specific adapters in `app/services/scrapers/`:
- `app/services/scrapers/intermarche_cart.py` (existing baseline)
- `app/services/scrapers/carrefour_cart.py` (new adapter)
- `app/services/scrapers/leclerc_cart.py` (new adapter)
- `app/services/scrapers/auchan_cart.py` (new adapter)

The core mirror service (`app/services/cart_mirror.py`) will dispatch operations by `SupermarketStore` enum:
- `read_cart(session, store, user_id)`
- `add_item(session, store, user_id, cache_id, quantity)`
- `update_item_quantity(session, store, user_id, item_id, quantity)`
- `remove_item(session, store, user_id, item_id)`
- `clear_cart(session, store, user_id)`

### Rationale
- **Single Source of Truth**: The retailer website remains the canonical source of truth for the cart. Local database rows (`SupermarketCart`, `SupermarketCartItem`) are strictly mirrors updated after each successful remote transaction.
- **Atomic Failure Protection**: If any retailer call fails (expired cookie, out-of-stock item, anti-bot challenge), the local cart is NOT modified, preserving the last known valid state.
- **Seam for Testing**: Each store client follows an injectable client builder pattern (`build_<store>_cart_client`) that can be cleanly mocked and unit-tested without live network calls.

### Alternatives Considered
- *Local-only carts with batch push*: Rejected because users expect immediate feedback and inventory validation; batch pushes fail at checkout time when items are out of stock.
- *Headless browser automation (Playwright)*: Rejected because browser automation requires 10–20x more memory and CPU, has high latency (5–15s per action), and is fragile in headless server environments compared to direct HTTP APIs.

---

## 2. Retailer-Specific API Protocols

### A. Intermarché (Baseline)
- **Protocol**: JSON REST (`POST /api/service/panier/v1/stores/{store_id}/carts`).
- **Mechanism**: Delta events (`QUANTITY` +n / -1) with `lastSynchronizedCart` concurrency token.
- **Authentication**: Session cookies (`itm_pdv` containing store ID `ref`, customer UUID from session).
- **Clear**: `DELETE /api/service/panier/v1/customers/{customer_uuid}/carts`.

### B. Carrefour
- **Protocol**: JSON REST (`GET /api/cart`, `POST /api/cart/items`, `PATCH /api/cart/items/{itemId}`, `DELETE /api/cart/items/{itemId}`, `DELETE /api/cart`).
- **Mechanism**: Standard REST with JSON payloads. Product ID mapped from `SupermarketSearchCache.external_id` (EAN / offer ID) and store Drive context.
- **Authentication**: Encrypted cookies from companion extension, requiring `x-store-id` or Drive session.
- **Network**: Requests route through `proxy_pool.py` to navigate Cloudflare protection on data-center IPs.

### C. Leclerc Drive
- **Protocol**: Form-urlencoded wrapper around JSON (`POST https://{sous-domaine}/magasin-{plid}-{plid}-{slug}/panier.aspx`).
- **Mechanism**: Field `d` containing URL-encoded JSON:
  - Add: `{"eTypeAction": 1, "iIdProduit": item_id, "iQuantite": n, "sNoPointLivraison": plid}`.
  - Update/Remove: `{"eTypeAction": 2, "iIdProduit": item_id, "iQuantite": n, "sNoPointLivraison": plid}` (quantity 0 = remove).
  - Clear: `POST panier.aspx?op=3` with `d={}`.
- **Authentication & Context**: Requires selected store Drive (`fdN-courses.leclercdrive.fr`) resolved from `SupermarketStoreSelection` or base URL, with delivery point cookies.

### D. Auchan
- **Protocol**: JSON API (`GET https://api.auchan.fr/checkout/v1/carts/mine`, `POST https://www.auchan.fr/cart/update`, `POST https://api.auchan.fr/checkout/v1/carts/{cartId}/items`).
- **Mechanism**:
  - Add item: JSON payload with `productId`, `offerId`, `sellerId`, and `desiredQuantity`.
  - Update/Remove: Checkout item endpoint with `desiredQuantity` (0 for removal).
  - Clear: `DELETE https://api.auchan.fr/checkout/v1/carts/{cartId}?consentId={consentId}`.
- **Authentication & Context**: Session cookies including `lark-journey` (selected store journey ID) and `consentId`.

---

## 3. Agent Integration via Model Context Protocol (MCP)

### Decision
Expose supermarket cart operations as first-class tools in `app/mcp/server.py` and action handlers in `app/skill/actions.py`:
- `supermarket.get_cart(store)`: Retrieve cart contents and line totals for a store.
- `supermarket.list_carts()`: List carts across all stores.
- `supermarket.add_cart_item(store, cache_id, quantity)`: Add a product found in supermarket search.
- `supermarket.update_cart_item(store, item_id, quantity)`: Change line quantity.
- `supermarket.remove_cart_item(store, item_id)`: Remove a line item.
- `supermarket.clear_cart(store)`: Empty the cart.

### Rationale
- AI agents in AdamHUB frequently assist with meal planning, missing ingredient detection, and shopping list assembly. Exposing cart operations via MCP allows the assistant to turn meal plans directly into real supermarket baskets.
- All actions inherit `CurrentOrOwnerUser` authentication, ensuring 100% tenant isolation (a user's agent can only interact with that user's carts).

---

## 4. Web Interface & Store State Management

### Decision
Leverage the existing `cartsByStore` and `cartApi` abstractions in `web/src/store/groceryStore.ts` and `web/src/pages/GroceriesPage.tsx`. The frontend already provides store tabs (Intermarché, Carrefour, Leclerc, Auchan); by enabling mirror mode across all four stores in the backend API, the frontend immediately gains full live multi-store cart functionality without major UI rewrites.

### Rationale
- Uniform API contract (`/api/v1/supermarket/carts/{store}`) keeps frontend store code DRY and consistent.
- `extractCartErrorMessage` provides immediate feedback for session expiration or missing store selection across all store tabs.
