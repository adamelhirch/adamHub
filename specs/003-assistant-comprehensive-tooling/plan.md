# Implementation Plan: Assistant Comprehensive Tooling & Smart Scheduling

**Branch**: `003-assistant-comprehensive-tooling` | **Date**: 2026-09-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-assistant-comprehensive-tooling/spec.md`

## Summary

Expand the AdamHUB conversational assistant tooling and execution engine to achieve full domain coverage across recipe management, proactive calendar conflict resolution, supermarket drive search and cart interaction, end-to-end meal planning with pantry deficit restocking, and reversible cook confirmations. Introduce a collision detection and alternative slot engine in `calendar_hub.py`, expose rich recipe, supermarket, and pantry actions to `ASSISTANT_ALLOWED_ACTIONS`, and enforce strict semantic distinction in prompts and mock fallbacks so recipes are never misfiled as tasks.

## Technical Context

**Language/Version**: Python 3.12+ (Backend), TypeScript / React Native Expo (Mobile app `app-saas/`)  
**Primary Dependencies**: FastAPI, SQLModel (SQLAlchemy 2.0), Pydantic v2, httpx, psycopg / SQLite  
**Storage**: PostgreSQL (Production) / SQLite in-memory/tempfile (Automated Test Suite)  
**Testing**: pytest via `uv run --extra dev pytest` (Maintain 100% passing across 387+ tests)  
**Target Platform**: Linux/macOS server (API) + iOS/Android/Web (Expo SaaS Client)  
**Project Type**: Multi-tenant web service API + Mobile App + AI Agent tooling  
**Performance Goals**: Assistant conversational tool call execution < 500ms per local tool; conflict detection & alternative slot computation < 50ms; streaming response time to first token < 1s  
**Constraints**: Zero task misfiling for culinary recipes; non-bypassable timeline collision detection unless explicitly forced by user; 100% tenant-isolated tool execution  
**Scale/Scope**: ~15 new/updated assistant actions, 1 core calendar conflict engine, 1 comprehensive test suite  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principle I: Strict Multi-Tenant Data Isolation & Dual-Mode Auth (NON-NEGOTIABLE)**:
  Every action in `tool_dispatcher.py` and `actions.py` takes `session` and `user: CurrentOrOwnerUser`. Every query explicitly filters on `user_id == user.id`. Cross-tenant lookups and mutations return 404.
- [x] **Principle II: Truth-in-Store Retail Data & Live Mirroring**:
  Supermarket drive search and cart tools exclusively manipulate items linked to authentic `SupermarketSearchCache` records. No mocked or fabricated product IDs are permitted.
- [x] **Principle III: Invariant-Driven Pantry & Grocery State Transitions**:
  Pantry inventory decreases ONLY upon explicit cook confirmation (`recipe.confirm_cooked` or `meal_plan.confirm_cooked`). Unconfirming reverses deductions accurately using recorded `pantry_consumption` lots.
- [x] **Principle IV: UTC Everywhere & Non-Bypassable Timeline Validation**:
  All timestamps passed to or returned by calendar tools use ISO 8601 UTC. Collisions are verified against all timeline sources. Alternative slot suggestions are computed in UTC.
- [x] **Principle V: Test-First Quality Assurance & Contract Synchronization**:
  Comprehensive test suite created in `tests/test_assistant_comprehensive_tooling.py`. Domain schemas, action catalogs, and assistant documentation in `adamhub-assistant/` synchronized.

## Project Structure

### Documentation (this feature)

```text
specs/003-assistant-comprehensive-tooling/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── assistant-tools.md
│   └── assistant-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code Layout

```text
app/
├── api/
│   ├── assistant.py                         # Chat streaming endpoint & SSE loop
│   └── endpoints/recipes.py                 # REST routes for recipes
├── services/
│   ├── calendar_hub.py                      # Collision detection & alternative slots engine
│   ├── cook.py                              # Pantry consumption & reversible lots
│   ├── meal_planning.py                     # Meal plan deficit & grocery synchronization
│   └── assistant/
│       ├── context_builder.py               # Prompt construction with anti-task recipe rules
│       ├── openrouter_client.py             # OpenRouter client & deterministic test mocks
│       └── tool_dispatcher.py               # Whitelisted actions & execution dispatcher
├── skill/
│   └── actions.py                           # Action catalog & execution handlers
└── models/
    └── entities.py                          # SQLModel entities

tests/
├── test_assistant_chat.py
├── test_assistant_tools.py
└── test_assistant_comprehensive_tooling.py  # New comprehensive tooling test suite
```

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| None | All designs adhere strictly to existing Single-Context architecture and Constitution principles | N/A |
