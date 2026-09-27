# Implementation Plan: Pantry Stock Management, Ingredient Normalization & Open Food Facts Scanner

**Branch**: `009-pantry-stock-openfoodfacts` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-pantry-stock-openfoodfacts/spec.md`

## Summary

This feature resolves inventory ambiguity and unit inconsistencies across recipes and pantry stock, introduces direct numerical pantry stock editing, upgrades AI assistant guardrails to enforce physical measurability (`g`/`kg` for measurable proteins, `item` strictly for natural whole piece items), and implements a barcode scanning pipeline with Open Food Facts that cleans commercial marketing noise while preserving culinary specificity (e.g. "Pâtes penne"), complete with an interactive review and completion sheet.

## Technical Context

**Language/Version**: Python 3.12+ (FastAPI backend), TypeScript 5.9+ (Vite Web React & Expo Mobile React Native).

**Primary Dependencies**:
- Backend: FastAPI, SQLModel (SQLAlchemy 2.0 core), Pydantic v2, Alembic, `httpx` (for Open Food Facts API).
- Mobile (`app-saas`): Expo SDK 57, React Native 0.86, NativeWind 4.2, `expo-camera` (for barcode scanning), `@expo/vector-icons`.
- Web (`web`): React 19, Vite 7, TailwindCSS 4, Lucide React, Axios.

**Storage**: PostgreSQL (production/local default) and SQLite (in-memory/dev testing), with Alembic migrations. Local caching for Open Food Facts barcodes via dedicated cache table.

**Testing**:
- Backend: `uv run --extra dev pytest`
- Web SPA: `cd web && npm run lint && npm run build`
- Mobile SaaS: `cd app-saas && npm run typecheck && npm run lint`

**Target Platform**: Web browsers (desktop/mobile responsive) and iOS/Android devices (via Expo React Native).

**Project Type**: Multi-surface Web Service + Web SPA + Mobile Native App + Autonomous AI Tooling.

**Performance Goals**:
- Barcode lookup & cleaning response in < 2 seconds.
- Direct pantry stock update latency in < 200 milliseconds.
- Instant fallback to manual entry if device camera or network is unavailable.

**Constraints**:
- Strict multi-tenant isolation with indexed `user_id` foreign keys (Constitution Principle I).
- Invariant-driven pantry inventory transitions without negative quantities (Constitution Principle III).
- Metric units for physical measurability, banning cut nouns as units (Constitution Principle V).
- Synchronous contract updates across backend, MCP/AI assistant, and client surfaces (Constitution Principle V).

**Scale/Scope**:
- Single-tenant owner + multi-tenant SaaS accounts.
- ~500 pantry items per household.
- Free Open Food Facts API v2 integration compliant with User-Agent guidelines.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principle I: Strict Multi-Tenant Data Isolation & Dual-Mode Auth** — All new/updated endpoints (`GET /pantry/barcode/{barcode}`, `PATCH /pantry/items/{id}`, `POST /pantry/items`) resolve `user: CurrentOrOwnerUser` and scope mutations strictly to `user.id`. Cross-tenant lookups return 404.
- [x] **Principle II: Truth-in-Store Retail Data & Live Mirroring** — Open Food Facts metadata is stored cleanly with brand and barcode references, leaving supermarket search cache and live store carts unpolluted.
- [x] **Principle III: Invariant-Driven Pantry & Grocery State Transitions** — Stock mutations are triggered exclusively by direct user adjustments or recipe cook deductions. Stock levels are strictly non-negative (`quantity >= 0`).
- [x] **Principle IV: UTC Everywhere & Non-Bypassable Timeline Validation** — Expiration dates and audit timestamps (`expires_at`, `created_at`, `updated_at`) are validated and serialized in UTC.
- [x] **Principle V: Test-First Quality Assurance & Contract Synchronization** — Full test coverage planned via pytest, typecheck, and lint gates. `context_builder.py`, `app/skill/actions.py`, and `adamhub-assistant/SKILL.md` are synchronized alongside backend models and frontend clients.

*Gates status: PASSED without exceptions.*

## Project Structure

### Documentation (this feature)

```text
specs/009-pantry-stock-openfoodfacts/
├── spec.md              # Feature specification
├── plan.md              # This implementation plan
├── research.md          # Research findings & architectural decisions
├── data-model.md        # Data models, schemas, and state transitions
├── quickstart.md        # Runnable verification guide
├── contracts/           # Interface contracts
│   ├── pantry-api.md    # REST API endpoints & payloads
│   └── assistant-tools.md # Assistant tool definitions & guardrails
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
app/
├── api/
│   └── pantry.py                   # Barcode lookup & enhanced item editing endpoints
├── models/
│   └── entities.py                 # OpenFoodFactsCache & PantryItem models
├── schemas/
│   └── pantry.py                   # OpenFoodFactsProductDraft & PantryItemUpdate
├── services/
│   ├── openfoodfacts.py            # Open Food Facts client, caching & cleaning algorithm
│   ├── units.py                    # Unit normalization & physical measurability rules
│   └── assistant/
│       └── context_builder.py      # AI Assistant guardrails & prompt instructions
└── skill/
    ├── actions.py                  # pantry.lookup_barcode action registration
    └── handlers/
        └── pantry.py               # Assistant handler for barcode lookups

scripts/
└── fix_user_recipes_and_pantry_saumon.py # One-time data correction for recipes & pantry

tests/
├── test_openfoodfacts_pantry.py    # Unit & integration tests for Open Food Facts & stock
├── test_ingredient_normalization.py# Unit tests for physical measurability & unit normalization
└── test_grocery_pantry_flow.py     # Pantry stock mutation & cook deduction tests

app-saas/
├── package.json                    # Added expo-camera dependency
└── src/
    ├── app/
    │   ├── (tabs)/pantry.tsx       # Enhanced pantry list with direct keypad edit sheet & scan button
    │   ├── new-pantry.tsx          # Barcode scan integration & pre-fill intake
    │   └── barcode-scanner.tsx     # Camera barcode scanner screen / modal
    └── lib/
        ├── api.ts                  # lookupBarcode API client
        └── pantry.ts               # Extended pantry mutations & types

web/
└── src/
    ├── pages/
    │   └── GroceriesPage.tsx       # Web pantry editing modal & manual barcode lookup
    └── store/
        └── groceryStore.ts         # Pantry stock update actions & barcode lookup
```

**Structure Decision**: Multi-surface structure spanning FastAPI backend (`app/`), mobile client (`app-saas/`), and web SPA (`web/`), adhering to existing module patterns and test boundaries.

## Complexity Tracking

*No violations of the Constitution. Standard patterns reused.*
