# Tasks: Connect Multi-Store Supermarket Carts

**Feature**: Connect Multi-Store Supermarket Carts  
**Branch**: `001-connect-supermarket-carts`  
**Input Documents**: [`spec.md`](spec.md), [`plan.md`](plan.md), [`data-model.md`](data-model.md), [`research.md`](research.md), [`contracts/`](contracts/)

---

## Phase 1: Setup (Shared Infrastructure & Fixtures)

**Purpose**: Establish test fixtures and mock datasets for retailer cart APIs.

- [X] T001 Verify baseline test execution for existing cart services with `uv run --extra dev pytest tests/test_supermarket_cart.py`
- [X] T002 [P] Create Carrefour mock cart response fixtures in `tests/fixtures/carrefour/cart_response.json`
- [X] T003 [P] Create Leclerc Drive mock cart response fixtures in `tests/fixtures/leclerc/cart_response.json`
- [X] T004 [P] Create Auchan mock cart response fixtures in `tests/fixtures/auchan/cart_response.json`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared error taxonomy, store capability registry, and common mirror client seams.

**⚠️ CRITICAL**: Must complete before user story implementation begins.

- [X] T005 Define generic cart mirror exceptions (`SupermarketCartError`, `SupermarketCartAuthError`, `SupermarketCartStoreContextError`, `SupermarketCartNotFoundError`) in `app/services/cart_mirror.py`
- [X] T006 [P] Update store capabilities in `app/services/store_catalog.py` to set `supports_cart_automation = True` across Carrefour, Leclerc, and Auchan

**Checkpoint**: Foundation ready - user story implementation can begin.

---

## Phase 3: User Story 1 - Live Multi-Store Cart Synchronization (Priority: P1) 🎯 MVP

**Goal**: Extend live cart mirroring across Carrefour, Leclerc, Auchan, and Intermarché. Remote retailer baskets act as the authoritative source of truth, and local database rows in `SupermarketCart` and `SupermarketCartItem` strictly mirror remote items.

**Independent Test**: Configure an active connection for each store and verify via API/tests that item additions, quantity adjustments, and removals update the remote store and reconcile the local mirror.

### Tests for User Story 1 ⚠️

- [X] T007 [P] [US1] Unit tests for Carrefour cart adapter in `tests/test_carrefour_cart.py`
- [X] T008 [P] [US1] Unit tests for Leclerc Drive cart adapter in `tests/test_leclerc_cart.py`
- [X] T009 [P] [US1] Unit tests for Auchan cart adapter in `tests/test_auchan_cart.py`
- [X] T010 [P] [US1] Multi-store integration tests for mirror operations in `tests/test_supermarket_cart_mirror.py`

### Implementation for User Story 1

- [X] T011 [P] [US1] Implement Carrefour cart client adapter with proxy pool support in `app/services/scrapers/carrefour_cart.py`
- [X] T012 [P] [US1] Implement Leclerc Drive form-urlencoded cart client adapter in `app/services/scrapers/leclerc_cart.py`
- [X] T013 [P] [US1] Implement Auchan checkout API cart client adapter in `app/services/scrapers/auchan_cart.py`
- [X] T014 [US1] Generalize multi-store dispatcher for `read_cart`, `add_item`, `update_item_quantity`, `remove_item`, and `clear_cart` in `app/services/cart_mirror.py`
- [X] T015 [US1] Implement duplicate item accumulation logic (increment existing quantity on add) in `app/services/cart_mirror.py`
- [X] T016 [US1] Update cart endpoints in `app/api/endpoints/supermarket.py` to route all store carts through `cart_mirror`

**Checkpoint**: User Story 1 is fully functional. All 4 supermarkets mirror live carts via REST API.

---

## Phase 4: User Story 2 - AI Agent Cart Interaction via Assistant Tools (Priority: P2)

**Goal**: Expose cart management capabilities (`get_cart`, `list_carts`, `add_cart_item`, `update_cart_item`, `remove_cart_item`, `clear_cart`) to AI agents through MCP and the skill action catalog, scoped to the acting user.

**Independent Test**: Execute MCP tool calls for an authenticated user to query carts, add missing ingredients, and verify that the cart updates remotely while retaining `draft` status.

### Tests for User Story 2 ⚠️

- [X] T017 [P] [US2] Contract and scoping tests for supermarket cart MCP tools in `tests/test_mcp_cart_tools.py`

### Implementation for User Story 2

- [X] T018 [US2] Implement supermarket cart action handlers (`supermarket.get_cart`, `list_carts`, `add_cart_item`, `update_cart_item`, `remove_cart_item`, `clear_cart`) in `app/skill/actions.py`
- [X] T019 [US2] Register supermarket cart MCP tools and schemas in `app/mcp/server.py`
- [X] T020 [P] [US2] Document agent cart actions and workflows in `adamhub-assistant/groceries/SKILL.md` and `adamhub-assistant/references/action-catalog.md`

**Checkpoint**: User Stories 1 AND 2 are complete. Agents can manage multi-store carts via MCP.

---

## Phase 5: User Story 3 - Interactive Web Interface for Multi-Store Carts (Priority: P3)

**Goal**: Provide a responsive web UI where users can toggle between all 4 store tabs, view live items, adjust quantities, remove items, clear carts, and receive clear onboarding prompts if a store is unconnected.

**Independent Test**: Navigate to `/groceries` > Panier tab in the web browser, switch between store tabs, perform cart operations, and verify responsive feedback and guidance banners.

### Implementation for User Story 3

- [X] T021 [US3] Update store actions, state management, and error handling in `web/src/store/groceryStore.ts`
- [X] T022 [US3] Update Panier tab in `web/src/pages/GroceriesPage.tsx` to support store-specific carts, quantity loading states, and unconnected store guidance banners

**Checkpoint**: User Stories 1, 2, and 3 are complete. Web users can interact with live carts across all stores.

---

## Phase 6: User Story 4 - Resilient Error Recovery & Actionable Guidance (Priority: P4)

**Goal**: Graceful error handling for expired retailer sessions, missing store/Drive selections, and network issues, preserving local cart data without corruption.

**Independent Test**: Simulate expired cookies or missing store location and verify that operations reject cleanly with instructions without wiping previously mirrored cart lines.

### Implementation for User Story 4

- [X] T023 [US4] Add error recovery tests for session expiration and missing store context in `tests/test_supermarket_cart_mirror.py`
- [X] T024 [US4] Refine user-facing error messages and recovery prompts in `app/services/cart_mirror.py` and `web/src/store/groceryStore.ts`

**Checkpoint**: All 4 user stories complete with resilient error recovery.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation synchronization, full regression testing, and build verification.

- [X] T025 [P] Update reverse-engineering documentation with cart endpoints in `docs/supermarket-reverse-engineering.md`
- [X] T026 Execute full backend test suite with `uv run --extra dev pytest`
- [X] T027 Execute frontend typecheck and build with `cd web && npm run lint && npm run build`
- [X] T028 Validate end-to-end scenarios per `specs/001-connect-supermarket-carts/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user stories.
- **User Story 1 (Phase 3 - P1 MVP)**: Depends on Phase 2. Core prerequisite for Stories 2 and 3.
- **User Story 2 (Phase 4 - P2)**: Depends on Phase 3 (needs working cart mirror service).
- **User Story 3 (Phase 5 - P3)**: Depends on Phase 3 (needs working cart mirror API).
- **User Story 4 (Phase 6 - P4)**: Depends on Phases 3, 4, 5.
- **Polish (Phase 7)**: Depends on all user stories being complete.

---

## Parallel Execution Opportunities

```bash
# Phase 1 Fixtures (Parallel):
Task T002: Carrefour fixtures
Task T003: Leclerc fixtures
Task T004: Auchan fixtures

# Phase 3 Adapters & Unit Tests (Parallel):
Task T007 & T011: Carrefour adapter and tests
Task T008 & T012: Leclerc adapter and tests
Task T009 & T013: Auchan adapter and tests

# Phase 4 & Phase 5 (Parallel once Phase 3 completes):
Developer / Worker A: User Story 2 (MCP & Agent tooling)
Developer / Worker B: User Story 3 (Web UI GroceriesPage)
```

---

## Implementation Strategy

### MVP Scope (User Story 1 Only)
1. Complete Phase 1 (Setup) and Phase 2 (Foundational).
2. Implement Phase 3 (Carrefour, Leclerc, Auchan adapters + `cart_mirror.py` dispatcher).
3. Validate User Story 1 with `uv run --extra dev pytest tests/test_supermarket_cart_mirror.py`.
4. Deploy / Merge MVP increment.

### Incremental Delivery
- Increment 1: User Story 1 (Live Multi-Store Cart Mirroring backend API).
- Increment 2: User Story 2 (AI Agent MCP tools & Skill catalog).
- Increment 3: User Story 3 (Web UI multi-store cart management).
- Increment 4: User Story 4 (Resilient error diagnostics & Polish).
