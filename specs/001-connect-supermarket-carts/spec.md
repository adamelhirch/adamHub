# Feature Specification: Connect Multi-Store Supermarket Carts

**Feature Branch**: `001-connect-supermarket-carts`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description: "Connecter les paniers des autres supermarchés comme on l'a fait avec intermarché afin de permettre à l'utilisateur via l'interface ainsi qu'aux agents via le mcp d'intéragir avec les differents paniers des utilisateurs"

## Clarifications

### Session 2026-09-11
- Q: How should the system handle adding an item that is already present in the target supermarket cart? → A: Increment the existing quantity by the requested amount (e.g., 2 + 1 = 3).
- Q: How should the web interface and agent tools handle a supermarket when the user has not yet connected an active session or selected a store location? → A: Keep the store selectable in the interface and return a descriptive status prompting the user to connect credentials or select a store location.
- Q: When an AI agent modifies a cart (such as assembling ingredients from a meal plan), should the cart status remain as draft or automatically change to validated? → A: Retain draft status so the user can review and make manual edits prior to checkout.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Live Multi-Store Cart Synchronization (Priority: P1)

Users want their shopping cart within the application to act as an accurate, live mirror of their actual cart on each supported supermarket website (Carrefour, Leclerc, Auchan, and Intermarché). When a user views or modifies their cart for any connected store, the application communicates directly with the retailer to reflect the real-world cart state immediately.

**Why this priority**: This is the foundational capability of the feature. Without live cart synchronization across all supported stores, neither human users nor automated AI agents can reliably manage grocery baskets.

**Independent Test**: Can be tested by configuring credentials for each store, adding an item via the application, and verifying that the item immediately appears with the correct quantity and price on the retailer's official website or application, and that the local view matches the remote cart.

**Acceptance Scenarios**:

1. **Given** an active, connected session for Carrefour, Leclerc, or Auchan, **When** the user requests the cart contents, **Then** the application reads the live cart from the retailer website and presents all current items, quantities, and totals.
2. **Given** a connected supermarket cart, **When** the user adds a product from search results, **Then** the product is added directly to the retailer's live cart, and the local cart updates to match the retailer's refreshed state.
3. **Given** an existing line item in a store cart, **When** the user increases, decreases, or zeroes its quantity, **Then** the quantity change is executed on the retailer site, and the updated line totals and overall cart total are displayed.
4. **Given** a store cart with multiple items, **When** the user chooses to clear the cart, **Then** the cart is emptied on the retailer site and the local cart reflects zero items.

---

### User Story 2 - AI Agent Cart Interaction via Assistant Tools (Priority: P2)

AI agents assisting users with meal planning, recipes, and dietary goals need to interact directly with the user's supermarket carts on their behalf. The assistant can view cart contents, add missing ingredients from approved recipes or meal plans, adjust quantities, and clear carts without manual copy-pasting by the user.

**Why this priority**: Enabling autonomous assistance transforms the application from a passive shopping list into an active life assistant. Delegating grocery cart assembly to agents saves significant time for users.

**Independent Test**: Can be tested by prompting an agent in a user session to "Add all missing ingredients for this week's dinner meal plan to my Carrefour cart", verifying that the agent queries the cart, adds the appropriate items, and reports the resulting cart summary with line items and total price.

**Acceptance Scenarios**:

1. **Given** an authenticated user session, **When** an AI agent requests the cart for a specified store, **Then** the agent receives a structured summary containing all cart items, quantities, prices, and status.
2. **Given** an item from authentic retailer search results, **When** an AI agent instructs the system to add the item with a specified quantity, **Then** the item is added to the user's live supermarket cart, the cart retains `draft` status for user review, and the agent receives confirmation of the updated cart total.
3. **Given** an existing item in the cart, **When** an AI agent updates the item quantity or removes it, **Then** the modification is performed on the live retailer site and the agent receives the updated cart state.
4. **Given** a request to reset or empty a cart, **When** an AI agent executes a clear cart command, **Then** the remote cart is emptied and the agent receives an empty cart confirmation.

---

### User Story 3 - Interactive Web Interface for Multi-Store Carts (Priority: P3)

In the web interface, users want a dedicated, responsive cart experience where they can switch between supported supermarket tabs (Intermarché, Carrefour, Leclerc, Auchan), see store-specific badges and totals, modify quantities in real time, remove items, and see their order total update dynamically.

**Why this priority**: Provides the primary human-facing control center where users inspect and finalize what agents or they themselves have placed into their baskets before proceeding to retailer checkout.

**Independent Test**: Can be tested by navigating to the Groceries/Cart page in a web browser, toggling between retailer tabs, adding and removing products, and confirming that UI controls (quantity increment/decrement, remove item, empty cart) respond with instant feedback and accurate error notifications if network or session issues occur.

**Acceptance Scenarios**:

1. **Given** multiple connected stores, **When** the user switches between store tabs in the cart view, **Then** the interface displays the specific cart for the selected store with its respective items, pricing, and status.
2. **Given** a cart line item in the web interface, **When** the user clicks the quantity adjustment controls, **Then** the interface shows a loading indicator during the remote update, followed by the refreshed quantity and total amount.
3. **Given** an item in the cart, **When** the user clicks the delete button, **Then** the line disappears from the list and the cart total decreases accordingly.
4. **Given** a populated cart, **When** the user clicks the "Clear Cart" button and confirms the dialog, **Then** all items are removed from the interface and the empty cart placeholder is shown.
5. **Given** a supermarket chain without an active connection or store location, **When** the user selects that store's tab, **Then** the interface displays an informative banner explaining that the store is not connected and provides guidance on importing credentials via the companion browser extension.

---

### User Story 4 - Resilient Error Recovery & Actionable Guidance (Priority: P4)

When retailer interactions fail due to expired sessions, unselected store branches, anti-bot challenges, or temporary network interruptions, the user and agent must receive clear, actionable diagnostic information. The local cart state must remain safe and uncorrupted, never presenting fabricated or speculative data.

**Why this priority**: Supermarket websites frequently invalidate sessions or require specific store locations. Without robust error handling and clear remediation prompts, users experience confusing failures and lost cart contents.

**Independent Test**: Can be tested by attempting a cart operation with intentionally expired cookies or without selecting a store branch, verifying that the operation is rejected with a clear explanation and that the previously known local cart items remain intact without corruption.

**Acceptance Scenarios**:

1. **Given** an expired or invalid store connection, **When** a user or agent attempts any cart mutation, **Then** the operation is rejected with a clear message instructing the user to refresh their connection via the browser extension, and the existing local cart data is left unmodified.
2. **Given** a store that requires an active branch/Drive selection where none is configured, **When** a cart operation is initiated, **Then** the system prompts the user to select their store location before proceeding.
3. **Given** an item that has become unavailable or out-of-stock at the retailer, **When** an addition or quantity update is attempted, **Then** the system informs the user or agent of the item's unavailability without breaking other items in the cart.

---

### Edge Cases

- **Expired Retailer Session**: If retailer authentication expires mid-session, cart mutations fail gracefully, the local cart is retained without destructive overwrites, and the user receives a targeted notification to re-authenticate.
- **Product Out-of-Stock during Addition**: If a product found in search is out-of-stock when added to the cart, the retailer's rejection is captured and communicated cleanly to the caller without affecting existing cart lines.
- **Missing Store Location**: For retailers requiring a local branch selection (e.g. Leclerc Drive or Auchan Drive) to compute prices and stock, cart operations cannot proceed until a valid store branch is established.
- **Unconnected Store Navigation**: Navigating to a store tab or querying a cart for an unconnected supermarket provides an informative state with instructions to connect rather than failing silently or locking the interface.
- **Concurrent Modifications**: If a user modifies their cart on the retailer's official website while also using the application, the next read or mutation operation reconciles against the retailer's current state.
- **Zero Quantity Handling**: Requesting a quantity of zero on an item must automatically translate into an item removal rather than leaving invalid or negative quantities in the basket.
- **Duplicate Item Addition**: If an item being added to a cart is already present, the system accumulates the quantity (existing + added) on the retailer site and local mirror.
- **Multi-Tenant Boundaries**: An authenticated user or agent must never be able to inspect, modify, or empty a supermarket cart belonging to another user.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST support live cart synchronization for all four supported supermarket retailers: Intermarché, Carrefour, Leclerc, and Auchan.
- **FR-002**: The system MUST treat the retailer's live cart as the authoritative source of truth, synchronizing the local state to match the remote response after each read or mutation.
- **FR-003**: The system MUST NOT modify the local cart state if a remote cart mutation fails, preventing discrepancies between the local view and the retailer's actual basket.
- **FR-004**: Users and AI agents MUST be able to retrieve the complete contents of a user's cart for any supported store, including product names, quantities, unit prices, line totals, currency, and overall basket total.
- **FR-005**: Users and AI agents MUST be able to add items to a supermarket cart using authentic product identifiers obtained from supermarket search results. If the item is already present in the target cart, the system MUST increment the existing quantity by the requested amount rather than overwriting it or returning an error.
- **FR-006**: The system MUST reject any cart addition that attempts to use arbitrary or fabricated product metadata not originating from genuine retailer catalog data.
- **FR-007**: Users and AI agents MUST be able to update the quantity of any existing item in a supermarket cart.
- **FR-008**: Users and AI agents MUST be able to remove an individual item from a supermarket cart.
- **FR-009**: Users and AI agents MUST be able to empty an entire supermarket cart in a single atomic action.
- **FR-010**: AI agents interacting via assistant tools MUST be able to perform all cart actions (read, add, update quantity, remove, clear) strictly scoped to the authenticated user.
- **FR-011**: All cart operations MUST strictly isolate data between users such that no user or agent can view or alter another user's cart.
- **FR-012**: When a store session is missing, expired, or rejected by the retailer, the system MUST return an actionable error explaining the cause and the remedy (such as re-importing cookies via the extension).
- **FR-013**: For retailers that require a specific physical branch or Drive selection to access the cart, the system MUST require and enforce a valid store context before executing cart operations.
- **FR-014**: The web interface MUST allow users to switch between all supported supermarket chains; if a selected store lacks an active connection or location context, the interface MUST display an informative prompt guiding the user to connect their account rather than hiding or disabling the tab.
- **FR-015**: All timestamps associated with cart synchronization, updates, and creation MUST be stored and communicated in UTC.
- **FR-016**: Automated cart modifications executed by AI agents MUST retain the cart in `draft` status, ensuring that final validation and checkout approval remain under the human user's direct control.

### Key Entities *(include if feature involves data)*

- **Supermarket Cart**: Represents a user's active shopping basket for a specific supermarket retailer. Tracks the store identity, the owning user, the current status (defaults to and remains `draft` across automated mutations until explicitly validated by the user), line item count, total price, and the last synchronization timestamp.
- **Cart Item**: An individual product entry within a supermarket cart. Contains the retailer's internal product identifier, product name, quantity, unit price, total line price, and optional product image URL.
- **Supermarket Connection**: The authenticated credentials and session context (encrypted at rest) associated with a user for a specific retailer, enabling authorized communication with the retailer's platform.
- **Store Location Context**: The specific retail branch, Drive point, or service area associated with the connection or user, determining local product availability and pricing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of successful cart operations (add, update quantity, remove, clear) performed in the application or by agents accurately reflect on the retailer's live website within 5 seconds under normal network conditions.
- **SC-002**: AI agents can independently inspect a user's cart, add multiple missing recipe ingredients, and verify the resulting basket total with zero manual user intervention on connected stores.
- **SC-003**: 0% cart data loss or state divergence: when a remote retailer operation fails (e.g. expired session or network timeout), the local cart retains its last verified state without data corruption.
- **SC-004**: 100% of session or configuration errors (missing connection, expired session, missing store selection) provide explicit, human-readable guidance indicating the exact recovery action needed.
- **SC-005**: 100% tenant isolation across all cart operations: cross-user cart access attempts return no information and produce zero data leaks.

## Assumptions

- Users import their retailer session credentials or cookies through the official browser extension, which are securely encrypted upon receipt.
- A physical store branch (Drive) has been designated or is present in the imported session for retailers where pricing and catalog availability are location-dependent.
- Supermarket retailer APIs and web endpoints maintain functional availability and do not permanently revoke online ordering capabilities.
- AI agents operate within authenticated user contexts and execute cart actions only in response to explicit user instructions or automated grocery workflows approved by the user.
- Checkout finalization, payment submission, and order delivery scheduling remain external steps completed by the user directly on the retailer's official website or app for security and legal compliance.
