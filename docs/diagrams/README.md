# Diagrams

Self-contained HTML/SVG diagrams of the SaaS-MVP domain flows, built with the
diagram-design skill conventions (paper `#f5f5f5`, ink `#2d3142`, accent
`#eb6c36`). Open in any browser.

- [`meal-planning-flow.html`](meal-planning-flow.html) — how a Recipe becomes a planned meal (one plan per slot per day), syncs missing ingredients to Groceries, and consumes/restores Pantry stock on confirm/unconfirm cooked.
- [`groceries-pantry-sync.html`](groceries-pantry-sync.html) — the GroceryItem ↔ PantryItem relationship: check restocks via `GroceryPantrySync`, uncheck reverses it, and Pantry stock is consumed directly or by cook confirmation.
- [`supermarket-connections.html`](supermarket-connections.html) — how a per-store `SupermarketConnection` (Fernet-encrypted cookies) powers the scraper into `SupermarketSearchCache`, and how `SupermarketMapping` durably links target rows — store metadata is always resolved server-side.
- [`dual-mode-auth.html`](dual-mode-auth.html) — how a request resolves to an Acting user: valid JWT Bearer → that user, else valid X-API-Key → `ADAMHUB_OWNER_EMAIL` Owner, else 401; both paths converge downstream.
