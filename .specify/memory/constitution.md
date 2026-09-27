<!--
Sync Impact Report:
- Version change: 0.0.0 (template) → 1.0.0
- List of modified principles:
  - [PRINCIPLE_1_NAME] → I. Strict Multi-Tenant Data Isolation & Dual-Mode Auth (NON-NEGOTIABLE)
  - [PRINCIPLE_2_NAME] → II. Truth-in-Store Retail Data & Live Mirroring
  - [PRINCIPLE_3_NAME] → III. Invariant-Driven Pantry & Grocery State Transitions
  - [PRINCIPLE_4_NAME] → IV. UTC Everywhere & Non-Bypassable Timeline Validation
  - [PRINCIPLE_5_NAME] → V. Test-First Quality Assurance & Contract Synchronization
- Added sections:
  - Architecture & Tenancy Constraints
  - Development Workflow & Quality Gates
  - Governance
- Removed sections:
  - None
- Follow-up TODOs:
  - None (all placeholders resolved from codebase rules and architecture documents)
-->

# AdamHUB Constitution

## Core Principles

### I. Strict Multi-Tenant Data Isolation & Dual-Mode Auth (NON-NEGOTIABLE)
Every persistent domain entity MUST belong to exactly one Tenant and possess an indexed `user_id` foreign key.
- Multi-tenant API requests MUST resolve the acting user via `CurrentOrOwnerUser` in `app/api/deps.py` (JWT tokens resolve to the specific authenticated SaaS user; shared `X-API-Key` resolves to the Owner account `ADAMHUB_OWNER_EMAIL`).
- Cross-tenant lookups, mutations, and deletions MUST return HTTP 404 (never HTTP 403) to prevent existence leakage.
- Administrative endpoints without per-tenant partitioning (such as `/api/v1/skill/execute` and `dashboard.overview`) MUST enforce `require_owner_only`.
- System-wide batch tasks (e.g. background notification loops) MUST explicitly execute in `user_id=None` system context or via administrative scripts.

*Rationale*: AdamHUB operates simultaneously as the Owner's personal operations hub and as a multi-tenant SaaS platform. Universal tenant scoping guarantees strict privacy boundaries for subscribers while preserving legacy developer workflows through single-source dependency resolution.

### II. Truth-in-Store Retail Data & Live Mirroring
Store-backed items across Groceries, Pantry, and Recipe Ingredients MUST originate from genuine retailer product data recorded in `SupermarketSearchCache`, NEVER from client-fabricated or mocked metadata.
- Remote retailer cart synchronizations (e.g. Intermarché) MUST treat the live retailer service as the authoritative source of truth. Local database records (`SupermarketCart`, `SupermarketCartItem`) act as mirrors and MUST be reconciled against remote response payloads after every write operation.
- External retailer credentials and browser cookies imported via the extension MUST be encrypted at rest using Fernet before storage in `SupermarketConnection`.
- Scraper operations MUST route through the shared residential proxy pool (`app/services/proxy_pool.py`) when anti-bot protections require it, falling back cleanly to direct access or cooldown without unhandled exceptions.

*Rationale*: Grocery operations interface directly with physical fulfillment centers and monetary transactions. Fabricated identifiers or stale cart states cause checkout failures, basket rejection, and degraded user trust.

### III. Invariant-Driven Pantry & Grocery State Transitions
Pantry inventory levels MUST ONLY mutate through three explicit triggers: explicit user stock adjustments, checking a grocery item (restock), or confirming a recipe or meal plan as cooked (`recipe.confirm_cooked` / `meal_plan.confirm_cooked`).
- Marking a grocery item as `checked` MUST generate a `GroceryPantrySync` link row recording the exact quantity restocked into the matching pantry item.
- Unchecking a grocery item MUST strictly reverse that restock using the recorded `GroceryPantrySync` entry and remove the sync link.
- Scheduling a meal plan MUST NEVER decrement pantry inventory prematurely; stock depletion occurs exclusively upon explicit cook confirmation and MUST be reversible via unconfirmation.

*Rationale*: Household inventory tracking quickly loses user confidence if state transitions produce side-effects out of sequence, or if unchecking shopping items fails to roll back automated pantry additions.

### IV. UTC Everywhere & Non-Bypassable Timeline Validation
All dates, timestamps, reminder schedules, and timeline slots across persistence, business logic, and API payloads MUST be stored and transmitted in UTC (`YYYY-MM-DDTHH:MM:SSZ`).
- Timezone translation is strictly a client-side presentation concern.
- Overlap collision validation in `app/services/calendar_hub.py` is NON-BYPASSABLE. Any domain event scheduled onto the unified timeline (tasks, meals, fitness sessions, calendar events, subscriptions) MUST pass through slot collision checks scoped to the acting user.
- Public calendar subscriptions (`/calendar/feed/{token}.ics`) MUST resolve their scope from the owning feed's `user_id`.

*Rationale*: Calendar serves as the shared coordinator across personal tasks, meal plans, fitness, and events. Timezone ambiguities and silent overlapping bookings destroy schedule coherence.

### V. Test-First Quality Assurance & Contract Synchronization
Code quality and multi-surface integrity MUST be enforced through continuous testing and strict ubiquitous domain language.
- All backend modifications MUST be verified with automated test suites using `uv run --extra dev pytest`, maintaining zero test failures.
- Frontend modifications in `web/` MUST pass `npm run lint` and `npm run build`; changes in `app-saas/` MUST pass `npm run typecheck` and `npm run lint`.
- Whenever a backend domain capability is added or revised for AI consumption, developers MUST synchronously update three artifacts: the domain schema and service (`app/schemas/`, `app/services/`), the skill manifest and execution handlers (`app/skill/actions.py`, `app/mcp/server.py`), and the assistant documentation (`adamhub-assistant/SKILL.md` and action catalogs).
- All models, tests, APIs, and PRs MUST strictly adopt the terminology defined in `CONTEXT.md` (e.g. `RecipeIngredient`, `Cook confirmation`, `Checked`, `Restock`, `Tenant`, `Acting user`), avoiding prohibited colloquialisms.

*Rationale*: Operating across a FastAPI backend, Vite React SPA, React Native Expo client, and an AI assistant platform leads to rapid drift unless contract synchronization and domain definitions are non-negotiable.

## Architecture & Tenancy Constraints

The system architecture adheres to a clean separation of concerns and uniform tenancy enforcement:
- **Backend Stack**: Python 3.12+, FastAPI, SQLModel (SQLAlchemy 2.0 core), Alembic for schema migrations, and Pydantic v2.
- **Database Migrations**: All schema modifications MUST be additive. Migrations must support both upgrade and downgrade paths and provide backfill mechanisms (e.g. `scripts/backfill_owner_tenant.py`) for existing records.
- **Domain Modeling**: The repository adheres to the Single-Context architecture described in `CONTEXT.md` and `docs/adr/`. Any substantive architectural evolution MUST be recorded as an Architecture Decision Record in `docs/adr/`.
- **Security & Privacy**: User secrets, external retailer cookies, and credentials MUST be encrypted at rest with Fernet encryption. Application API keys and JWT signing secrets MUST NEVER be committed to version control.

## Development Workflow & Quality Gates

Every feature and bug fix follows a disciplined progression from specification to integration:
- **Issue Tracking**: All work items, refactors, and feature specs are tracked via GitHub Issues (`gh issue`), adhering to `docs/agents/issue-tracker.md`.
- **Pre-Commit / Pre-Merge Gates**:
  - Backend: `uv run --extra dev pytest` (exit code 0).
  - Web SPA: `cd web && npm run lint && npm run build` (exit code 0).
  - Mobile SaaS: `cd app-saas && npm run typecheck && npm run lint` (exit code 0).
- **Code Review**: Pull requests MUST be reviewed for strict adherence to multi-tenant isolation, anti-fabrication of store items, UTC enforcement, and invariant-driven state transitions.
- **Git History**: Commits and pull requests MUST reference the corresponding issue number and be squash-merged to preserve a clear, linear history.

## Governance

This Constitution represents the supreme architectural and development policy for AdamHUB.
- **Supremacy**: The principles and constraints established herein supersede local convenience, ad-hoc practices, and informal pull request conventions.
- **Amendment Procedure**: Amendments to this Constitution require an explicit pull request documenting:
  1. The exact principles or sections added, modified, or repealed.
  2. Concrete rationale and cross-surface impact analysis (Backend, Web, SaaS app, AI Assistant).
  3. A migration plan for existing code and test suites.
  All amendments require formal approval and ratification by the repository owner.
- **Versioning Policy**: This Constitution follows Semantic Versioning (`MAJOR.MINOR.PATCH`):
  - **MAJOR**: Incompatible governance shifts, removal or fundamental redefinition of core principles.
  - **MINOR**: Addition of new principles, quality gates, or substantially expanded architectural guidance.
  - **PATCH**: Clarifications, non-semantic wording improvements, and typo corrections.
- **Compliance**: All automated agents, developers, and reviewers MUST verify that proposed changes satisfy this Constitution prior to merging.

**Version**: 1.0.0 | **Ratified**: 2026-09-11 | **Last Amended**: 2026-09-11
