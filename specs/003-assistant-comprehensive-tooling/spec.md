# Feature Specification: Assistant Comprehensive Tooling & Smart Scheduling

**Feature Branch**: `003-assistant-comprehensive-tooling`

**Created**: 2026-09-12

**Status**: Draft

**Input**: User description: "Outillage complet de l'assistant IA (recettes, supermarché, garde-manger, gestion d'erreurs calendrier). Définir le périmètre complet des capacités d'outillage de l'assistant IA (CRUD recettes, planification de repas, gestion de stocks, recherche et panier supermarché, tâches, calendrier). Spécifier la gestion élégante des conflits de créneaux calendrier (détection de chevauchement, proposition de décalage ou écrasement explicite). Définir les parcours utilisateurs, critères d'acceptation, cas limites et critères de succès agnostiques de la tech."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Full Recipe Lifecycle & Semantic Coherence (Priority: P1)

As an active user managing household meals, I want to ask the assistant to create, view, search, edit, and delete culinary recipes with structured ingredients and instructions, so that my culinary repertoire is accurately organized in the recipe system rather than misfiled as generic to-do tasks.

**Why this priority**: When users dictate recipes, the assistant currently falls back to creating tasks or reporting a lack of capabilities. Recipes represent the foundational data model required for meal planning, automated grocery generation, and dietary compliance.

**Independent Test**: Can be tested by instructing the assistant: *"Enregistre ma recette de Risotto aux champignons : 300g de riz arborio, 250g de champignons de Paris, 1 oignon, 1L de bouillon. Cuisson 25 min à feu doux"*, verifying that a structured recipe entity is created with discrete ingredient items, and asking *"Quelles sont mes recettes de risotto ?"* to retrieve the exact structured recipe card without any task being created.

**Acceptance Scenarios**:

1. **Given** an authenticated user in a conversation with the assistant, **When** the user says *"Crée une recette de Salade César pour 2 personnes avec 200g de poulet, de la romaine et 30g de parmesan"*, **Then** the assistant saves the recipe with the specified servings, title, and ingredient lines, and returns a structured recipe confirmation card without creating any task.
2. **Given** existing recipes in the user's library, **When** the user asks *"Qu'est-ce que j'ai comme recettes rapides pour le dîner ?"*, **Then** the assistant queries the user's recipe library, filters by preparation or cooking duration, and lists matching recipes with their key ingredients and durations.
3. **Given** an existing recipe, **When** the user requests *"Ajoute 1 gousse d'ail aux ingrédients de mon Risotto aux champignons"*, **Then** the assistant updates the existing recipe's ingredient list without duplicating the recipe.
4. **Given** an existing recipe, **When** the user asks *"Supprime la recette de Salade César"*, **Then** the assistant requests confirmation before deleting the recipe, and upon confirmation removes it safely.

---

### User Story 2 - Smart Calendar Conflict Detection & Proactive Resolution (Priority: P1)

As a busy individual managing a crowded schedule, I want the assistant to detect calendar and timeline slot collisions when scheduling events, tasks, meals, or workouts, and proactively suggest alternative open time slots or offer explicit resolution options, so that my schedule remains collision-free without cryptic error messages.

**Why this priority**: A scheduling assistant that crashes with an overlap error or silently rejects booking degrades user trust. Proactively identifying conflicts and proposing the next best available time window turns a point of friction into an intelligent assistant experience.

**Independent Test**: Can be tested by creating an event from 14:00 to 15:00, asking the assistant *"Planifie une séance de sport demain de 14:30 à 15:30"*, and verifying that the assistant flags the 30-minute overlap with the existing event, identifies the conflicting title, and proposes alternative non-overlapping slots (e.g. 15:00 to 16:00 or 13:00 to 14:00).

**Acceptance Scenarios**:

1. **Given** an existing calendar event from 10:00 to 11:30 tomorrow, **When** the user asks *"Ajoute un rendez-vous dentiste demain de 10:30 à 11:30"*, **Then** the assistant detects the overlap, informs the user of the conflict with the existing event, and suggests the earliest compatible open windows (e.g., 11:30–12:30 or 09:00–10:00).
2. **Given** a proposed alternative slot for a conflicting item, **When** the user replies *"D'accord pour 11h30"*, **Then** the assistant creates the event at the accepted alternative time and confirms the updated schedule.
3. **Given** a detected conflict where the user intentionally wants simultaneous events, **When** the user explicitly commands *"Force l'ajout quand même sur ce créneau"*, **Then** the assistant proceeds with the explicit scheduling and notes that the slot contains overlapping commitments.
4. **Given** a user requesting to schedule an event without specifying a time (e.g. *"Planifie 1h d'étude demain après-midi"*), **When** the assistant searches for open slots, **Then** it identifies unoccupied periods between existing commitments and proposes the optimal open slot before confirming.

---

### User Story 3 - Supermarket Drive Search & Cart Integration (Priority: P2)

As a household manager, I want the assistant to search genuine retailer products from supported supermarket drives (such as Intermarché, Carrefour, Leclerc, and Auchan) and manage my online shopping cart, so that I can prepare my real-world grocery orders directly through conversational instructions.

**Why this priority**: Bridging digital planning with physical fulfillment requires authentic retailer product data and live cart interaction. Fabricating mock products or lacking drive capabilities forces users to leave the platform to perform manual searches.

**Independent Test**: Can be tested by asking *"Recherche du lait demi-écrémé bio chez Intermarché"*, verifying that real cached retailer products with prices and packaging are returned, then instructing *"Ajoute le premier pack à mon panier drive"*, verifying that the item is reflected in the active retailer cart.

**Acceptance Scenarios**:

1. **Given** an active retailer connection for the user, **When** the user asks *"Cherche des pâtes complètes chez Carrefour"*, **Then** the assistant searches the store catalog, returns genuine matching products with name, brand, price, and unit price, and asks if the user wants to add any to their cart.
2. **Given** a search result with a known product, **When** the user asks *"Mets 2 paquets de ces pâtes dans mon panier drive"*, **Then** the assistant adds the authentic product reference to the user's active supermarket cart and confirms the updated cart quantity and total price.
3. **Given** an active supermarket cart containing items, **When** the user asks *"Qu'est-ce qu'il y a dans mon panier Intermarché ?"*, **Then** the assistant displays the live cart contents, item counts, unit prices, and overall total.
4. **Given** an item in the supermarket cart, **When** the user asks *"Retire le paquet de café de mon panier"*, **Then** the assistant updates the remote cart and confirms the removal.

---

### User Story 4 - End-to-End Meal Planning & Deficit Restocking (Priority: P2)

As an organized planner, I want to ask the assistant to plan my meals for the upcoming days, verify what ingredients are already in my pantry, and automatically add only the missing ingredients to my grocery list or drive cart, so that I never double-buy ingredients I already have.

**Why this priority**: The key value of an integrated life hub is cross-domain synergy: linking recipes, meal planning, pantry stock checks, and grocery lists into one unified autonomous workflow without manual copying across separate screens.

**Independent Test**: Can be tested with a pantry containing 500g of pasta and 0 eggs, instructing the assistant *"Planifie des pâtes carbonara pour jeudi soir"*, verifying that the meal is scheduled, 500g pasta is detected as available, and only the missing ingredients (eggs, guanciale, pecorino) are added to the grocery shopping list.

**Acceptance Scenarios**:

1. **Given** a planned recipe requiring multiple ingredients, **When** the user instructs *"Planifie le dîner de vendredi avec la recette Curry de poulet"*, **Then** the assistant schedules the meal on Friday evening, verifies pantry inventory, and provides a breakdown of ingredients in stock versus ingredients missing.
2. **Given** missing ingredients identified during meal planning, **When** the user confirms adding missing items to groceries, **Then** the assistant creates only the needed grocery items with their respective quantities, without duplicating items already in sufficient stock.
3. **Given** a meal scheduled during an already occupied time slot, **When** the assistant attempts to book the meal slot, **Then** the assistant flags the schedule overlap and proposes a non-conflicting time or prompts for confirmation.

---

### User Story 5 - Reversible Cook Confirmation & Pantry Inventory Synchronization (Priority: P3)

As a home cook, I want to confirm to the assistant when a planned meal or recipe has been cooked, so that my pantry stock is accurately decremented, and have the ability to reverse this confirmation if marked by mistake.

**Why this priority**: Maintaining accurate pantry stock depends on recording real consumption. However, users frequently make accidental taps or change dinner plans at the last minute; reversible inventory transitions prevent inventory drift.

**Independent Test**: Can be tested by confirming a recipe as cooked, verifying that the associated pantry ingredient levels decrease by the recipe's ingredient quantities, then instructing *"Annule la confirmation de cuisson"*, verifying that the pantry quantities are precisely restored to their previous levels.

**Acceptance Scenarios**:

1. **Given** a scheduled meal plan or saved recipe with 200g of rice and 2 cans of tuna, and a pantry with 1000g rice and 5 cans of tuna, **When** the user says *"J'ai cuisiné le repas de ce soir"*, **Then** the assistant confirms the cook state, decrements the pantry to 800g rice and 3 cans of tuna, and records the confirmation.
2. **Given** a confirmed cook state, **When** the user says *"Je me suis trompé, annule la cuisson de ce plat"*, **Then** the assistant restores the exact consumed quantities back into the pantry and resets the meal/recipe state.
3. **Given** a recipe requiring an ingredient not tracked in the pantry, **When** cook confirmation is triggered, **Then** the assistant consumes all tracked pantry items and reports the untracked items gracefully without failing the operation.

---

### Edge Cases

- **Ambiguous Recipe Titles**: If the user asks to plan or cook a recipe with a generic title matching multiple recipes (e.g. "Tarte aux pommes"), the assistant MUST list the matching recipes with creation dates or ingredients and ask the user to clarify before taking action.
- **Negative or Zero Quantities**: If a user or recipe specifies a zero or negative quantity for an ingredient or grocery item, the assistant MUST reject the quantity with an explanatory message and ask for a valid positive amount.
- **Store Connectivity Drop / Expired Session**: If an action attempts to query or modify a supermarket drive cart when retailer credentials or cookies are expired, the assistant MUST notify the user clearly that their store connection needs renewal rather than crashing or showing technical stack traces.
- **Extreme Calendar Overlap (Back-to-Back Busy Day)**: If a requested day is completely booked with zero open slots of the required duration, the assistant MUST inform the user that no open slots exist on that date and suggest the closest available slots on adjacent days.
- **Partial Cook Confirmation (Insufficient Stock)**: If the pantry has less quantity than required by a recipe (e.g. recipe needs 300g, pantry has 100g), the assistant MUST decrement the pantry stock to zero without creating negative inventory, and inform the user of the shortfall.
- **Simultaneous Action Failures in Multi-Step Flows**: In a chained flow (e.g. create recipe -> schedule meal -> add groceries), if the scheduling step detects an unresolved conflict, the previously created recipe MUST remain safely saved, and the assistant MUST resume from the scheduling step without restarting the entire flow from scratch.

## Requirements *(mandatory)*

### Functional Requirements

#### Recipe & Culinary Management
- **FR-001**: The assistant MUST support full conversational creation of recipes including name, optional description, instructions or structured steps, prep/cook duration, servings, and ingredient lines.
- **FR-002**: The assistant MUST support querying and listing recipes by search terms, ingredient availability, tags, and preparation time limits.
- **FR-003**: The assistant MUST support updating existing recipe details (servings, steps, ingredient adjustments) while maintaining data integrity.
- **FR-004**: The assistant MUST require explicit user confirmation before executing recipe deletion.
- **FR-005**: The assistant MUST NEVER classify or save a cooking recipe as a task or generic note.

#### Pantry & Inventory Tracking
- **FR-006**: The assistant MUST allow users to query current pantry stock, including low-stock and out-of-stock items.
- **FR-007**: The assistant MUST allow users to add new items to the pantry, adjust quantities, and manually record consumed quantities.
- **FR-008**: Marking a grocery item as purchased/checked MUST increment the matching pantry item stock, and unchecking MUST reversibly deduct that exact increment.
- **FR-009**: Confirming a recipe or meal plan as cooked MUST decrement matching pantry inventory items proportionally to the recipe servings.
- **FR-010**: Reversing a cook confirmation MUST restore the exact decremented quantities back into the pantry.

#### Supermarket Drive & Retailer Cart Operations
- **FR-011**: The assistant MUST allow users to search for authentic grocery products across supported supermarket retailers using live retailer search cache data.
- **FR-012**: The assistant MUST NOT fabricate, invent, or mock product identifiers, brands, or prices for supermarket items.
- **FR-013**: The assistant MUST allow users to view their active supermarket drive cart, including item quantities, prices, and cart total.
- **FR-014**: The assistant MUST allow users to add authentic search-derived products to their active supermarket drive cart, update item quantities, and remove items.
- **FR-015**: The assistant MUST inform users when a retailer connection requires login renewal or store selection before cart operations can proceed.

#### Smart Calendar Scheduling & Conflict Handling
- **FR-016**: The assistant MUST validate slot availability across the unified timeline whenever scheduling calendar items, tasks with allocated time, meal plans, or workouts.
- **FR-017**: When a requested time slot overlaps with one or more existing items, the assistant MUST NOT fail with a raw unhandled error; it MUST detect the collision and identify the title and timeframe of the conflicting item(s).
- **FR-018**: Upon detecting a schedule conflict, the assistant MUST automatically compute and propose at least two non-overlapping alternative slots (e.g. earliest available slot after the conflict, or closest open slot on the same day).
- **FR-019**: The assistant MUST support three explicit resolution paths for detected conflicts: accepting a suggested alternative slot, specifying a custom time, or forcing concurrent scheduling if explicitly confirmed by the user.
- **FR-020**: All scheduled items MUST be validated and stored using UTC timestamps, while dates and times in conversational dialogues MUST be communicated in the user's localized perspective.

#### Unified Multi-Action Orchestration
- **FR-021**: The assistant MUST support chained autonomous execution for complex lifestyle prompts (e.g. recipe creation followed by meal planning, pantry deficit analysis, and grocery list generation).
- **FR-022**: Following any multi-action execution, the assistant MUST present a consolidated summary card clearly displaying each action completed, items modified, and any open suggestions.
- **FR-023**: Every assistant tool call and data mutation MUST be strictly scoped to the authenticated tenant/user; cross-user data leakage or mutation MUST be strictly impossible.

### Key Entities *(include if feature involves data)*

- **Recipe**: Represents a culinary preparation. Attributes include unique identifier, owning user identifier, name, description, instructions/steps, preparation duration, cooking duration, servings count, tags, and associated recipe ingredients.
- **Recipe Ingredient**: A discrete component of a recipe. Attributes include name, target quantity, unit of measurement, category, optional note, and optional link to authentic supermarket product cache.
- **Pantry Item**: Represents physical food stock currently held by the user. Attributes include name, current quantity, unit, storage location/category, expiration date, and minimum restock threshold.
- **Grocery Item**: Represents an item needed for shopping. Attributes include name, desired quantity, unit, checked status, and link to a restocked pantry item.
- **Supermarket Product**: Real-world product from a supported retailer. Attributes include authentic retailer product reference, name, brand, package size, unit price, and total price.
- **Supermarket Cart & Cart Item**: Represents the user's remote and mirrored retailer shopping basket. Attributes include retailer name, active connection identifier, line items with product reference, quantities, and subtotal.
- **Calendar Item**: Represents a scheduled slot on the unified timeline. Attributes include title, description, start timestamp in UTC, end timestamp in UTC, category (general, task, meal, workout, event), and completion status.
- **Meal Plan**: Represents a scheduled consumption of a recipe or custom dish on the timeline. Attributes include date, meal slot (breakfast, lunch, dinner, snack), recipe reference, servings, and cooked confirmation status.
- **Schedule Conflict**: Ephemeral detection entity generated during scheduling. Attributes include proposed time window, list of colliding items (title, start timestamp, end timestamp), and suggested open alternative windows.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of user requests to save recipes result in structured recipe entities; 0% are misfiled as tasks or rejected with missing tool errors.
- **SC-002**: When a calendar slot collision occurs, 100% of responses identify the conflicting item by title and present at least one viable non-overlapping alternative slot instead of a raw failure message.
- **SC-003**: Users can complete an end-to-end weekly meal planning prompt (incorporating 3+ recipes, scheduling, pantry check, and grocery additions) in under 15 seconds of assistant interaction time.
- **SC-004**: 100% of products added to supermarket drive carts originate from verified retailer search data with authentic retailer pricing, eliminating fabricated items.
- **SC-005**: User task completion rate for resolving scheduling conflicts on first prompt exchange exceeds 90%.
- **SC-006**: 100% of pantry deductions from confirmed meals can be cleanly reversed without manual user inventory reconciliation.

## Assumptions

- The user has an active, authenticated account within their isolated tenant.
- Supermarket search and cart operations require prior configuration of supported store connections (via saved credentials or extension cookie import); if no connection exists, the assistant gracefully explains how to connect a store.
- Calendar availability checks examine all timeline sources (manual calendar entries, time-allocated tasks, scheduled meals, and workout sessions) belonging to the user.
- Natural language time expressions (e.g. "demain midi", "ce soir à 20h") are interpreted relative to the user's current local date, time, and timezone, then translated to UTC for system validation.
- All operations adhere strictly to multi-tenant isolation; no user can ever inspect or alter recipes, schedules, pantry stocks, or carts of another tenant.
