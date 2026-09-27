# Implementation Plan: Recipe App Interactions (Cooking Confirmation, Groceries Restock, and Smart Calendar Scheduling)

**Branch**: `008-recipe-app-interactions` | **Date**: 2026-09-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/008-recipe-app-interactions/spec.md`

---

## Summary

This feature delivers complete, gesture-driven and transactional recipe interactions across the mobile application (`app-saas`) and FastAPI backend:
1. **Swipe Interactions on Recipe Cards (Expo `kitchen.tsx`)**:
   - Progressive left swipe: short drag triggers « Cuisiné maintenant » (immediate pantry stock decrement); full drag triggers « Planifier » (calendar scheduling modal).
   - Right swipe triggers « Ajouter aux courses » opening a bottom sheet with checkable ingredients (missing items pre-checked by default).
2. **Tactile Deficit Feedback**:
   - When cooking with partial or missing pantry items, card performs a Reanimated shake animation + haptic vibration, decumulates available stock down to 0 (no negative inventory), and presents a 1-tap toast to restock the deficit into groceries.
3. **Smart Collision-Free Calendar Scheduling**:
   - `POST /api/v1/meal-plans` dynamically calculates duration from `prep_minutes + cook_minutes` (defaulting to 45 min) and checks timeline collisions via `detect_calendar_conflicts_and_alternatives`.
   - If occupied (e.g. 17:00–18:00 appointment), direct scheduling is blocked with HTTP 409 returning colliding items and >= 2 viable alternative slots.
4. **Interactive Portions Stepper & Instructions Editing**:
   - Stepper (+/-) dynamically scales all ingredient amounts on the mobile recipe detail screen (`/recipe/[id]`).
   - Instructions and preparation steps can be edited in place.

---

## Technical Context

**Language/Version**: Python 3.12 (Backend), TypeScript 5.7+ (Mobile SaaS & Web)  
**Primary Dependencies**:
- Backend: FastAPI, SQLModel, Pydantic v2, SQLAlchemy 2.0
- Mobile (`app-saas`): React Native 0.86, Expo 57, Expo Router v4, NativeWind v4, `react-native-gesture-handler`, `react-native-reanimated`
- Web (`web`): React 18, Vite, Lucide React, TailwindCSS  
**Storage**: PostgreSQL (production), SQLite `tmp_path` (isolated automated testing)  
**Testing**:
- Backend: `uv run --extra dev pytest tests/test_recipe_app_interactions.py -v` (full suite: `uv run --extra dev pytest`)
- Mobile SaaS: `cd app-saas && npm run typecheck && npm run lint`
- Web: `cd web && npm run build && npm run lint`  
**Target Platform**: iOS & Android (Expo app-saas), Modern Web Browsers, Dockerized Linux backend  
**Project Type**: Fullstack Mobile SaaS  
**Performance Goals**: 60fps/120fps gesture fluidity, < 100ms client-side portions scaling, < 200ms calendar collision response  
**Constraints**:
- Strict multi-tenant isolation (`user_id` foreign key)
- Invariant-driven pantry mutations (clamped at 0, reversible uncooking)
- UTC timestamps everywhere (`YYYY-MM-DDTHH:MM:SSZ`)
- Non-bypassable calendar collision validation  
**Scale/Scope**: 4 primary user stories, 5 endpoints, 3 interactive mobile components.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Multi-Tenant Isolation)**: PASS. All recipe, grocery, pantry, and meal plan mutations require `CurrentOrOwnerUser` and scope SQLModel queries to `user_id`.
- **Principle II (Truth-in-Store Data)**: PASS. Ingredients added to groceries retain existing store metadata (`store`, `external_id`, `product_url`) without fabricating synthetic identifiers.
- **Principle III (Pantry Invariants)**: PASS. Pantry stock depletions occur exclusively upon explicit cook confirmation, clamp at 0 without negative quantities, and unconfirming cook restores exact lots.
- **Principle IV (UTC & Timeline Validation)**: PASS. All `planned_at` timestamps are stored in UTC. Calendar overlap collision checking is strictly enforced on recipe scheduling.
- **Principle V (Test-First QA)**: PASS. Dedicated test suites in `tests/test_recipe_app_interactions.py`, 0 type errors in `app-saas`.

---

## Project Structure

### Documentation (this feature)

```text
specs/008-recipe-app-interactions/
├── spec.md              # Feature specification & clarifications
├── plan.md              # Implementation plan (this file)
├── research.md          # Technical decisions & rationale
├── data-model.md        # Entities, DTOs, and state transitions
├── contracts/
│   └── recipe-interactions-api.md # API & UI contracts
├── quickstart.md        # Validation & execution guide
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code Layout

```text
app/
├── api/
│   ├── recipes.py           # Add POST /recipes/{id}/add-to-groceries
│   └── meal_plans.py        # Dynamic duration & calendar collision check
├── models/
│   └── entities.py          # Recipe, RecipeIngredient, PantryItem, GroceryItem, MealPlan
├── schemas/
│   └── meal_planning.py     # DTOs for grocery addition & calendar conflict payloads
└── services/
    ├── calendar_hub.py      # Sync meal plan using recipe prep+cook duration
    ├── cook.py              # Partial stock deduction & lot restoration
    └── meal_planning.py     # Deficit calculations & grocery restock

app-saas/
├── src/
│   ├── app/
│   │   ├── (tabs)/
│   │   │   └── kitchen.tsx  # Swipeable recipe cards & shake animations
│   │   └── recipe/
│   │       └── [id].tsx     # Portions stepper, inline editing, cook/plan buttons
│   ├── components/
│   │   ├── recipe-card-swipeable.tsx  # Progressive gesture handling
│   │   ├── recipe-groceries-sheet.tsx # Checkable ingredients modal
│   │   └── recipe-plan-modal.tsx      # Collision-aware scheduling dialog
│   └── lib/
│       ├── api.ts           # API client bindings
│       └── recipes.ts       # Recipe service helpers

tests/
└── test_recipe_app_interactions.py # Comprehensive test suite
```

---

## Complexity Tracking

No constitution violations detected. Standard layered architecture preserved across backend and frontend clients.
