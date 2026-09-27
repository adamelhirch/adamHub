# Research & Architectural Decisions: Mobile AI Agent & Context Engine

**Feature**: `002-mobile-ai-agent`
**Date**: 2026-09-12

---

## 1. LLM Orchestration & Streaming Architecture

### Decision
Implement a native Python service within FastAPI (`app/services/assistant/`) that interfaces with OpenRouter via asynchronous HTTP streaming (`httpx.AsyncClient`) and serves Server-Sent Events (SSE) to clients via FastAPI `StreamingResponse`.

### Rationale
- **Zero Third-Party Middleware Overhead**: Directly orchestrating LLM calls within FastAPI eliminates unnecessary layers (such as LibreChat or external Node.js proxy services).
- **Direct Database & Tenancy Access**: The FastAPI handler already resolves the authenticated `User` from the JWT token, allowing synchronous, in-process compilation of the user's active context without network hops or cross-service sync.
- **Interchangeable Models via OpenRouter**: Standard OpenAI-compatible format allows switching between Gemini 2.0 Flash (`google/gemini-2.0-flash-001`), DeepSeek V3 (`deepseek/deepseek-chat`), or other models via environment configuration (`ADAMHUB_AI_MODEL`).
- **Tool Calling (Function Calling)**: `app/skill/actions.py` already implements 70+ actions with schema definitions. The assistant maps these action schemas to OpenAI tool definitions and executes them locally in the user's database session.

### Alternatives Considered
- **LibreChat / External Agent Platform**: Rejected. Adds MongoDB and Node.js dependencies, creates user synchronization hurdles, and lacks direct access to the SQLModel database layer and local action execution catalog.
- **WebSockets instead of SSE**: Rejected. SSE is unidirectional (server-to-client streaming), naturally compatible with HTTP/2 and standard reverse proxies, and handles reconnection simply. Client inputs are standard POST requests.

---

## 2. Memory Architecture & Asynchronous Fact Extraction

### Decision
Adopt a **Two-Tier Decoupled Memory Architecture**:
1. **Live Conversational Tier**: Stream chat responses immediately to the user without blocking on memory indexing.
2. **Background Fact Extractor Tier**: Trigger a FastAPI `BackgroundTask` upon completion of response streaming. This task calls a fast, structured LLM prompt to identify durable facts and update the `UserMemory` table.

### Rationale
- **Zero Latency Penalty**: The user receives streaming tokens in < 500 ms without waiting for memory classification.
- **Focused Cognitive Responsibility**: The extraction model has a single, isolated objective: parse the turn for persistent user facts (health constraints, nutrition goals, lifestyle habits, preferences) and emit structured JSON (`add`, `update`, `revoke`).
- **Conflict & Contradiction Resolution**: Extracted facts are evaluated against existing active memories. If an update occurs (e.g. "injury healed"), previous contradictory memories are deactivated (`is_active = False`).
- **Transparency & User Agency**: Storing discrete memory entries allows rendering a user-facing "What the AI knows about you" screen where users can view and revoke memories.

### Alternatives Considered
- **Synchronous In-Stream Tool Calling (`save_memory`)**: Rejected as the primary mechanism because it interrupts fluid streaming responses on mobile and is frequently skipped by models when generating complex answers.
- **Full Chat Vector RAG**: Rejected for v1. User facts are discrete and finite (dozens or hundreds, not millions). Injecting a curated Markdown summary of active memories into the system prompt uses minimal context (~300 tokens) and avoids vector search retrieval inaccuracies.

---

## 3. Database Strategy: 100% PostgreSQL with Rootless Podman

### Decision
Completely deprecate SQLite across all environments (development, automated testing, production) and standardize on **PostgreSQL 16** managed locally via **Podman** (`podman compose` / `podman machine`).

### Rationale
- **100% Dev/Prod Parity**: Eliminates discrepancies between SQLite and PostgreSQL regarding JSON/JSONB data types, foreign key cascades, transaction concurrency, and Alembic schema migrations.
- **Concurrent Writer Scalability**: Essential for the background memory extractor, which writes memory rows while concurrent user requests and streaming threads access the database. SQLite file locks (`database is locked`) fail under this pattern.
- **Podman Daemonless Execution**: Podman runs rootless without a persistent background daemon draining CPU/battery on macOS, perfectly aligning with developer workflow requirements.

### Test Strategy
- Automated tests (`pytest`) connect to a dedicated test database (`adamhub_test`) running in the local Podman Postgres container.
- Table isolation between test runs is enforced via transaction rollbacks or rapid table truncation fixtures.

---

## 4. Mobile Client Integration (`app-saas`)

### Decision
Implement the Assistant interface as an Expo Router modal screen (`src/app/assistant.tsx`) triggered by the central button in the bottom navigation bar (`src/app/(tabs)/_layout.tsx`).

### Rationale
- **Native Touch Ergonomics**: Full-screen modal provides ample space for conversational streaming, keyboard management, quick-prompt pills, and action confirmation cards.
- **Ephemeral Session UX**: Messages live in React state / Zustand during the active session. A prominent "New Conversation" / "Clear" action wipes current thread state without touching the persistent `UserMemory` or `UserProfile`.
- **Action Confirmation Cards**: Tool execution events emitted via SSE render as rich interactive UI cards (e.g., created task with checkbox, added grocery item with quantity badge).
