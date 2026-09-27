# Implementation Plan: Connect Multi-Store Supermarket Carts

**Branch**: `001-connect-supermarket-carts` | **Date**: 2026-09-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from [`specs/001-connect-supermarket-carts/spec.md`](spec.md)

---

## Summary

Extend the real-time cart mirroring capability—previously established exclusively for Intermarché—across all four supported supermarket chains (**Intermarché, Carrefour, Leclerc, Auchan**). Retailer carts act as the authoritative source of truth: local database records in `SupermarketCart` and `SupermarketCartItem` strictly mirror remote retailer baskets, updated upon every successful transaction. Furthermore, expose full cart management capabilities to AI agents via the Model Context Protocol (MCP) and skill action catalog, while enabling multi-store cart switching and live controls in the React web application.

---

## Technical Context

**Language/Version**: Python 3.12+ (Backend), TypeScript 5+ (Frontend / Web)  
**Primary Dependencies**:
- Backend: FastAPI, SQLModel, Pydantic v2, HTTPX, BeautifulSoup4, cryptography (Fernet)
- Frontend: React 18, Vite, Zustand, Tailwind CSS  
**Storage**: PostgreSQL (production / staging), SQLite (local test suites). Additive migrations via Alembic.  
**Testing**: `uv run --extra dev pytest` (Backend unit/integration/mock tests), `npm run lint && npm run build` (Web).  
**Target Platform**: Linux / macOS containerized services, web modern browsers, local dev.  
**Project Type**: Multi-tier web service + AI Assistant MCP server + Single-Page Application (SPA).  
**Performance Goals**: Remote cart operations complete within 2–5 seconds under standard network conditions; local mirror reads respond in <50ms.  
**Constraints**:
- Strict multi-tenant isolation via `CurrentOrOwnerUser` (user-scoped data, 404 on cross-tenant access).
- Residential proxy routing via `app/services/proxy_pool.py` for bot-protected retailers.
- Encrypted credentials at rest via Fernet.
- Zero local cart state modification on remote failure.  
**Scale/Scope**: 4 supermarket retailers, 6 MCP tools, 6 REST endpoints, multi-store web UI.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I: Strict Multi-Tenant Data Isolation & Dual-Mode Auth (NON-NEGOTIABLE)**
  - *Status*: **PASSED**. All cart queries and mutations resolve the acting user via `CurrentOrOwnerUser` in `app/api/deps.py` and filter by `user_id`. Cross-tenant cart access returns HTTP 404. MCP tools are strictly scoped to the acting user.
- **Principle II: Truth-in-Store Retail Data & Live Mirroring**
  - *Status*: **PASSED**. Carts act as live mirrors of remote retailer platforms. Item additions require genuine cached search data from `SupermarketSearchCache`. Retailer cookies are encrypted at rest with Fernet.
- **Principle III: Invariant-Driven Pantry & Grocery State Transitions**
  - *Status*: **PASSED**. Shopping cart operations do not mutate pantry stock prematurely. State transitions are strictly isolated to cart entities.
- **Principle IV: UTC Everywhere & Non-Bypassable Timeline Validation**
  - *Status*: **PASSED**. All cart creation and update timestamps are stored and transmitted in UTC (`YYYY-MM-DDTHH:MM:SSZ`).
- **Principle V: Test-First Quality Assurance & Contract Synchronization**
  - *Status*: **PASSED**. Design synchronizes API schemas, MCP server tools (`app/mcp/server.py`), action catalog (`app/skill/actions.py`), and assistant docs (`adamhub-assistant/`). Comprehensive test suites cover all store adapters and mirror invariants.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-connect-supermarket-carts/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan
├── research.md          # Phase 0 architectural decisions & protocols
├── data-model.md        # Phase 1 data entities and mirror state machines
├── quickstart.md        # Phase 1 end-to-end validation guide
├── contracts/           # Phase 1 API and tool specifications
│   ├── rest-api.md      # REST endpoints for /api/v1/supermarket/carts
│   └── mcp-tools.md     # AI agent MCP tool schemas
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code Impact (repository root)

```text
app/
├── services/
│   ├── cart_mirror.py                  # Generalized multi-store mirror dispatcher
│   ├── cart.py                         # Local storage, cache row resolution, replace_items
│   └── scrapers/
│       ├── intermarche_cart.py          # Existing Intermarché cart adapter
│       ├── carrefour_cart.py            # [NEW] Carrefour JSON cart adapter
│       ├── leclerc_cart.py              # [NEW] Leclerc panier.aspx form adapter
│       └── auchan_cart.py               # [NEW] Auchan checkout API cart adapter
├── api/endpoints/
│   └── supermarket.py                  # Cart REST endpoints updated for multi-store mirror
├── mcp/
│   └── server.py                       # Expose supermarket.cart tools to AI agents
└── skill/
    └── actions.py                      # Register supermarket.cart action handlers

adamhub-assistant/
├── groceries/SKILL.md                  # Assistant grocery skill documentation
└── references/action-catalog.md        # Catalog reference for cart actions

web/
└── src/
    ├── pages/GroceriesPage.tsx         # Cart tab multi-store UI & error display
    └── store/groceryStore.ts           # Store actions & state management for multi-store

tests/
├── test_supermarket_cart_mirror.py     # Multi-store mirror integration tests
├── test_carrefour_cart.py              # [NEW] Unit tests for Carrefour cart adapter
├── test_leclerc_cart.py                # [NEW] Unit tests for Leclerc cart adapter
└── test_auchan_cart.py                 # [NEW] Unit tests for Auchan cart adapter
```

---

## Complexity Tracking

| Aspect | Justification | Alternatives Considered |
|---|---|---|
| Dedicated store adapters | Each retailer uses a distinct API architecture (Intermarché delta events, Carrefour JSON, Leclerc urlencoded JSON, Auchan checkout API). | Single monolithic adapter (rejected due to high coupling and maintainability issues). |
| Live remote mirroring | Ensures real basket synchronization and immediate validation of pricing and stock. | Local-only cart with delayed checkout push (rejected because stock/pricing divergences cause checkout rejection). |
