# Quickstart & Validation Guide: Mobile AI Agent & Context Engine

**Feature**: `002-mobile-ai-agent`
**Date**: 2026-09-12

---

## 1. Prerequisites

- macOS with Podman installed (`/opt/homebrew/bin/podman`)
- Python 3.12+ with `uv`
- Node.js 20+ with npm
- OpenRouter API key configured in `.env` (`ADAMHUB_OPENROUTER_API_KEY`)

---

## 2. Environment Setup (100% PostgreSQL with Podman)

### Start PostgreSQL container via Podman
```bash
# Ensure podman machine is running
podman machine start

# Start the PostgreSQL service in the background
podman compose up -d postgres

# Verify the container is healthy
podman ps
```

### Apply Database Migrations
```bash
# Apply migrations to local PostgreSQL instance
ADAMHUB_DB_URL=postgresql+psycopg://adamhub:adamhub@localhost:5432/adamhub uv run alembic upgrade head
```

---

## 3. Automated Test Execution

Execute the backend test suite verifying the Assistant API, Context Engine, Memory Extractor, and Multi-Tenant Isolation against PostgreSQL:

```bash
# Run pytest with PostgreSQL test database
ADAMHUB_ENV=test uv run --extra dev pytest tests/test_assistant_chat.py tests/test_user_memory.py -v
```

Execute mobile TypeScript typecheck:
```bash
cd app-saas && npm run typecheck
```

---

## 4. End-to-End Manual Verification Scenarios

### Scenario A: Start Local Services
1. In terminal 1 (FastAPI backend with PostgreSQL):
   ```bash
   ADAMHUB_ENV=development ADAMHUB_DB_URL=postgresql+psycopg://adamhub:adamhub@localhost:5432/adamhub uv run uvicorn app.main:app --reload --port 8000
   ```
2. In terminal 2 (React Native / Expo mobile app):
   ```bash
   cd app-saas && npm run start
   ```

### Scenario B: Personalized Context & Streaming
1. Open the mobile app in iOS/Android simulator.
2. Tap the central **AI Assistant** button in the bottom navigation bar.
3. Submit a prompt: *"Qu'est-ce que je pourrais manger ce midi en fonction de mes objectifs et de mes stocks ?"*
4. **Expected**:
   - Response tokens begin streaming progressively within 1.2 seconds.
   - The assistant references active user profile dietary goals and current pantry stock.

### Scenario C: Cross-Domain Action Execution
1. Send: *"Ajoute 1kg de bananes à ma liste de courses et prévois une séance jambes demain à 18h."*
2. **Expected**:
   - The assistant calls the respective actions (`grocery.item.create` and `calendar.event.create`).
   - Interactive confirmation cards render directly inside the chat thread showing the added grocery item and scheduled workout.

### Scenario D: Background Memory Extraction
1. Send: *"Au fait, je me suis blessé à l'épaule gauche, évite le développé couché pendant deux semaines."*
2. **Expected**:
   - The assistant answers immediately acknowledging the injury.
   - In the background, the memory extractor detects the injury and inserts a record into `user_memories` with `category='health_fitness'`.
   - Open Profile/Settings in the mobile app: the new fact appears under "Souvenirs enregistrés" with a delete button.

### Scenario E: Ephemeral Session Reset
1. Tap the "Nouvelle discussion" / "Reset" button at the top right of the assistant screen.
2. **Expected**:
   - The chat thread clears instantly (< 200 ms).
   - Asking *"De quelle blessure je souffre ?"* correctly retrieves the left shoulder injury from persistent `UserMemory`.
