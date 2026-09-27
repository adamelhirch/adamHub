# Implementation Plan: Mobile AI Agent & Context Engine

**Branch**: `002-mobile-ai-agent` | **Date**: 2026-09-12 | **Spec**: [specs/002-mobile-ai-agent/spec.md](file:///Users/adamelhirch/Documents/Projets%20perso/AdamHUB/specs/002-mobile-ai-agent/spec.md)

**Input**: Feature specification from `/specs/002-mobile-ai-agent/spec.md`

## Summary

Implement an autonomous, context-aware mobile AI assistant for AdamHUB backed by a Two-Tier Decoupled Memory Architecture:
1. **Live Conversational Streaming Tier**: Progressive SSE streaming token-by-token (< 1.2s TTFT) through OpenRouter (Gemini 2.0 Flash / DeepSeek V3), dynamically injecting persistent user profile facts and a real-time working memory snapshot (tasks, meals, pantry alerts) into the system prompt.
2. **Asynchronous Background Memory Extractor**: A lightweight background task running post-stream to parse conversations, identify durable user facts (injuries, habits, preferences), and populate the `UserMemory` table without impacting chat latency.
3. **100% PostgreSQL Standard with Podman**: Total deprecation of SQLite across all development and testing environments in favor of PostgreSQL 16 managed via Podman.
4. **Mobile Client Interface (`app-saas`)**: An Expo Router modal screen accessible via the central bottom navigation button featuring streaming markdown, interactive action cards, and one-tap session reset.

---

## Technical Context

**Language/Version**: Python 3.12 (Backend), TypeScript 5.4+ / Node.js 20+ (React Native / Expo)

**Primary Dependencies**:
- Backend: FastAPI, SQLModel / SQLAlchemy 2.0, Alembic, Pydantic v2, `httpx` (async HTTP/SSE to OpenRouter)
- Containerization: Podman 6.0.2 (`podman compose` / `podman machine`)
- Mobile: React Native 0.86, Expo 57, Expo Router, NativeWind (Tailwind), React Native Reanimated

**Storage**: PostgreSQL 16 (running in rootless Podman container)

**Testing**:
- Backend: `uv run --extra dev pytest` (running against PostgreSQL `adamhub_test`)
- Mobile: `cd app-saas && npm run typecheck && npm run lint`

**Target Platform**: iOS & Android (via React Native Expo) + Linux/macOS API server

**Project Type**: Mobile App + REST/SSE Web Service

**Performance Goals**:
- Time to First Token (TTFT): < 1.2 seconds on mobile client
- Background memory extraction latency: < 800 ms in async background worker
- Session reset latency: < 200 ms

**Constraints**:
- Strict multi-tenant data isolation (`user_id` on all entities)
- Zero SQLite usage in dev or test runs
- Daemonless Podman container orchestration

**Scale/Scope**: Multi-tenant personal operations SaaS with live streaming and autonomous memory extraction

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principle I: Strict Multi-Tenant Data Isolation & Dual-Mode Auth (NON-NEGOTIABLE)**
  - `UserProfile`, `UserMemory`, `AssistantSession`, and `AssistantMessage` all include an indexed `user_id` foreign key.
  - Endpoints in `/api/v1/assistant/*` resolve the user via `CurrentOrOwnerUser` dependency in `app/api/deps.py`. Cross-tenant access returns 404.
- [x] **Principle II: Truth-in-Store Retail Data & Live Mirroring**
  - Tool actions for groceries and pantry continue to route through canonical `app/skill/actions.py` handlers preserving store data integrity.
- [x] **Principle III: Invariant-Driven Pantry & Grocery State Transitions**
  - Cook confirmations, restocks, and checklist toggles triggered by the assistant respect domain invariants and generate appropriate sync records.
- [x] **Principle IV: UTC Everywhere & Non-Bypassable Timeline Validation**
  - All timestamps (`created_at`, `updated_at`, `current_time_utc`) are stored and calculated in UTC.
  - Any scheduling events created by assistant actions pass through non-bypassable slot collision validation in `app/services/calendar_hub.py`.
- [x] **Principle V: Test-First Quality Assurance & Contract Synchronization**
  - Automated tests verified with `uv run --extra dev pytest` on PostgreSQL.
  - Mobile verified with `cd app-saas && npm run typecheck && npm run lint`.
  - Action catalogs and OpenAPI contracts documented synchronously.

---

## Project Structure

### Documentation (this feature)

```text
specs/002-mobile-ai-agent/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── assistant-api.yaml
└── checklists/
    └── requirements.md
```

### Source Code (repository layout)

```text
# Backend (FastAPI + SQLModel)
app/
├── api/
│   ├── assistant.py            # [NEW] Endpoints: /chat (SSE), /profile, /memories, /session/reset
│   └── router.py               # Include assistant router
├── models/
│   └── entities.py             # [MODIFY] Add UserProfile and UserMemory entities
├── schemas/
│   └── assistant.py            # [NEW] Pydantic models for chat requests, profile, memories
├── services/
│   └── assistant/
│       ├── __init__.py         # [NEW]
│       ├── context_builder.py  # [NEW] Compiles live snapshot + persistent memories into system prompt
│       ├── openrouter_client.py# [NEW] Async client for LLM streaming and tool calls
│       └── memory_extractor.py # [NEW] Background task for fact extraction and memory consolidation
└── core/
    ├── config.py               # [MODIFY] Add OpenRouter settings (model, key, extraction model)
    └── db.py                   # [MODIFY] Enforce PostgreSQL configuration

# Database Migrations
alembic/versions/
└── xxx_add_user_profile_and_memory.py # [NEW] Alembic migration for UserProfile & UserMemory

# Test Suite (PostgreSQL via Podman)
tests/
├── conftest.py                 # [MODIFY] Configure PostgreSQL test engine fixtures
├── test_assistant_chat.py      # [NEW] Test SSE streaming, prompt injection, and tool calling
└── test_user_memory.py         # [NEW] Test background memory extraction and multi-tenant isolation

# Mobile Frontend (React Native Expo Router)
app-saas/
├── src/
│   ├── app/
│   │   ├── (tabs)/
│   │   │   └── _layout.tsx     # [MODIFY] Wire central AI assistant button
│   │   └── assistant.tsx       # [NEW] Full-screen assistant modal interface
│   ├── components/
│   │   ├── assistant/
│   │   │   ├── chat-message.tsx# [NEW] Bubble component with Markdown & streaming animation
│   │   │   ├── action-card.tsx # [NEW] Interactive action confirmation card
│   │   │   └── memory-tag.tsx  # [NEW] Memory item pill with dismiss button
│   │   └── screen.tsx
│   └── lib/
│       └── assistant-api.ts    # [NEW] Client wrapper for SSE streaming and memory management
```

---

## Complexity Tracking

| Decision | Why Needed | Simpler Alternative Rejected Because |
|:---|:---|:---|
| **Two-Tier Decoupled Memory** | User expects < 1s streaming response while requiring persistent personalization | In-stream synchronous memory extraction delays response streaming by 1-2s; vector RAG adds unnecessary embedding infrastructure for small personal fact lists |
| **100% PostgreSQL with Podman** | Concurrency locks and JSON syntax discrepancies break background memory workers and Alembic migrations | SQLite locks the entire database file during writes, preventing concurrent chat reads while the memory extractor commits |
