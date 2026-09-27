# Implementation Plan: End-to-End Browser Automation & System Accuracy Test Suite

**Branch**: `010-browser-e2e-accuracy-tests` | **Date**: 2026-09-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-browser-e2e-accuracy-tests/spec.md`

---

## Summary

Build an automated End-to-End (E2E) browser testing and system accuracy verification suite for AdamHUB. The suite enables visual observation of automated interactions in real browsers (`--headed` and Playwright `--ui`), audits retail matching accuracy (preventing absurd products like butter for salt or chicken broth for garlic), validates mathematical pantry invariants upon cook confirmations, and produces an automated accuracy and gap report (`docs/audit/e2e-accuracy-report.md`).

---

## Technical Context

**Language/Version**: TypeScript 5.9+ (frontend & E2E tests), Python 3.12+ (backend)  
**Primary Dependencies**: `@playwright/test`, React 19, FastAPI, SQLModel  
**Storage**: PostgreSQL / SQLite (`adamhub.db` / test fixtures), `SupermarketSearchCache`  
**Testing**: Playwright (`@playwright/test`) for browser E2E, pytest (`uv run --extra dev pytest`) for backend  
**Target Platform**: Modern desktop and mobile emulated browsers (Chromium, Firefox, WebKit) on macOS / Linux  
**Project Type**: Full-stack web application (FastAPI backend + Vite React SPA)  
**Performance Goals**: Smoke test suite completes in < 2 minutes; full benchmark execution in < 5 minutes  
**Constraints**: Zero data pollution of Owner personal data (strict test-tenant isolation); 100% retail category accuracy on canonical benchmarks; non-flaky resilient locators  
**Scale/Scope**: 5 core user journeys, 3 canonical benchmark recipes, 1 automated audit report generator  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- [x] **Principle I: Strict Multi-Tenant Data Isolation & Dual-Mode Auth (NON-NEGOTIABLE)**: The E2E suite creates and signs into a dedicated test tenant (`e2e-tester@adamelhirch.com`). All browser operations run within this tenant's scope, ensuring zero interference with the Owner's personal operations.
- [x] **Principle II: Truth-in-Store Retail Data & Live Mirroring**: Test assertions validate authentic products recorded in `SupermarketSearchCache` across Carrefour, Intermarché, and Leclerc, guaranteeing that no fabricated products or incompatible substitutes are staged.
- [x] **Principle III: Invariant-Driven Pantry & Grocery State Transitions**: The pantry invariant suite explicitly asserts stock transitions on `recipe.confirm_cooked`, unconfirm reversals, and grocery item check restocks.
- [x] **Principle IV: UTC Everywhere & Non-Bypassable Timeline Validation**: Any calendar timeline interactions scheduled during testing validate ISO 8601 UTC format.
- [x] **Principle V: Test-First Quality Assurance & Contract Synchronization**: The E2E suite runs as an automated quality gate without breaking existing backend unit tests or frontend builds.

---

## Project Structure

### Documentation (this feature)

```text
specs/010-browser-e2e-accuracy-tests/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Technical decisions & framework choices
├── data-model.md        # Entities, metrics & invariant audit structures
├── quickstart.md        # How to run headed/headless tests & read reports
└── contracts/
    ├── e2e-runner-api.md           # CLI commands & fixture contracts
    └── accuracy-report-schema.json # JSON Schema for audit reports
```

### Source Code (repository root)

```text
web/
├── playwright.config.ts                       # Playwright configuration (webServer, viewports, artifacts)
├── package.json                               # NPM scripts (test:e2e, test:e2e:headed, test:e2e:ui, smoke, accuracy)
└── tests/
    └── e2e/
        ├── fixtures/
        │   ├── auth.ts                        # Test tenant authentication fixture
        │   └── test-env.ts                    # Page fixture with seed/cleanup helpers
        ├── benchmarks/
        │   └── accuracy-cases.ts              # Canonical recipe matching benchmark assertions
        ├── reporters/
        │   └── accuracy-reporter.ts           # Custom reporter generating docs/audit/e2e-accuracy-report.md
        ├── smoke.spec.ts                      # Sub-2-minute sanity checks across primary navigation
        ├── supermarket-accuracy.spec.ts       # Recipe-to-Cart fidelity & strategy audit
        ├── pantry-invariants.spec.ts          # Inventory stock transitions & reversal verification
        └── assistant-guardrails.spec.ts       # AI assistant chat & metric constraints test

scripts/
└── run_e2e_tests.sh                           # Top-level shell script for headed/headless test runs

docs/
└── audit/
    └── e2e-accuracy-report.md                 # Generated audit report tracking accuracy & identified gaps
```

**Structure Decision**: Collocating the Playwright configuration and test specs directly inside `web/` leverages Vite's live dev server and shared TypeScript types, while `scripts/run_e2e_tests.sh` provides a top-level launcher that coordinates backend health and generates reports.

---

## Complexity Tracking

*No constitutional violations or unjustified architectural patterns.*
