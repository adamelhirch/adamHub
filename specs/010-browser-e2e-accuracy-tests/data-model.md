# Data Model: End-to-End Browser Automation & System Accuracy Test Suite

**Feature**: `010-browser-e2e-accuracy-tests`  
**Date**: 2026-09-18  

---

## 1. Entities & Structures

### `E2ETestRun`
Represents an entire execution session of the Playwright E2E and Accuracy test suite.

| Field | Type | Description |
| :--- | :--- | :--- |
| `run_id` | `string` (UUID) | Unique identifier for this test run |
| `timestamp` | `string` (ISO 8601 UTC) | Execution start timestamp |
| `duration_ms` | `number` | Total duration of the test run in milliseconds |
| `mode` | `string` | Execution mode: `headless`, `headed`, or `ui` |
| `viewport` | `string` | Tested viewport dimension, e.g. `1280x800` (desktop) |
| `total_tests` | `number` | Number of executed test specifications |
| `passed_tests` | `number` | Number of passed tests |
| `failed_tests` | `number` | Number of failed tests |
| `accuracy_rate` | `number` | Global percentage score of valid product matches ($\in [0, 100]$) |
| `anomalies_count`| `number` | Number of detected gaps or non-fatal anomalies |

---

### `AccuracyBenchmarkCase`
Represents a predefined benchmark recipe scenario used to assert supermarket cart staging fidelity.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `string` | Unique benchmark identifier (e.g. `dahl-lentilles-corail`) |
| `recipe_name` | `string` | Name of the recipe in database |
| `store` | `string` | Target retailer: `carrefour`, `intermarche`, `leclerc`, `auchan` |
| `strategy` | `string` | Selected optimization strategy: `budget`, `mdd`, `bio` |
| `expected_ingredients` | `Array<ExpectedItem>` | List of required ingredient assertions |
| `prohibited_items` | `Array<ProhibitedItemRule>` | Explicit negative assertions (products that must NEVER match) |

#### `ExpectedItem`
- `name`: string (e.g. "Lentilles corail")
- `required_qualifiers`: string[] (e.g. `["corail"]`)
- `expected_category`: string (e.g. "Féculents & Légumes secs")
- `allow_substitute`: boolean

#### `ProhibitedItemRule`
- `ingredient_name`: string (e.g. "Ail")
- `prohibited_terms`: string[] (e.g. `["volaille", "viande", "bouillon"]`)
- `reason`: string (e.g. "Garlic must not match chicken broth via substring")

---

### `AuditAnomalyRecord`
Structured record of any functional defect, UI gap, or performance regression identified during testing.

| Field | Type | Description |
| :--- | :--- | :--- |
| `anomaly_id` | `string` | Unique anomaly identifier (e.g. `GAP-001`) |
| `severity` | `string` | Severity rating: `P0` (blocker), `P1` (critical), `P2` (moderate), `P3` (minor / polish) |
| `category` | `string` | Functional area: `Drive Staging`, `Pantry`, `Recipe`, `Assistant`, `UI/UX` |
| `title` | `string` | Concise description of the gap or mismatch |
| `details` | `string` | Detailed technical context and reproduction steps |
| `reproduction_journey` | `string` | User story or test scenario that triggered the finding |
| `screenshot_path` | `string | null` | Path to the captured failure screenshot, if applicable |
| `status` | `string` | Current status: `detected`, `acknowledged`, `resolved` |

---

### `PantryInvariantAudit`
Tracks the mathematical verification of pantry stock transitions during cook and grocery actions.

| Field | Type | Description |
| :--- | :--- | :--- |
| `audit_id` | `string` | Unique check ID |
| `pantry_item_name`| `string` | Name of the verified inventory item (e.g. "Lentilles corail") |
| `initial_quantity`| `number` | Quantity before operation |
| `unit` | `string` | Measurement unit (`g`, `ml`, `item`) |
| `operation` | `string` | Operation type: `cook_confirm`, `cook_unconfirm`, `grocery_check`, `grocery_uncheck`, `manual_edit` |
| `delta_quantity` | `number` | Quantity applied by the operation |
| `expected_final_quantity` | `number` | Expected mathematical result |
| `actual_final_quantity` | `number` | Quantity retrieved from database after UI interaction |
| `is_consistent` | `boolean` | `true` if `expected_final_quantity == actual_final_quantity` |

---

## 2. Invariant & Validation Rules

1. **Category Isolation Invariant**: For any staged product matching ingredient $I$, the candidate product's head noun MUST NOT belong to `INCOMPATIBLE_HEAD_NOUNS[I.head_noun]`.
2. **Retail Accuracy Metric**:
   $$\text{Accuracy} = \frac{\sum \text{Valid Matches}}{\sum \text{Requested Items}} \times 100\%$$
   The accuracy benchmark test fails if $\text{Accuracy} < 100\%$.
3. **Pantry Reversibility Invariant**:
   $$\text{Stock}_{\text{after unconfirm}} = \text{Stock}_{\text{initial}}$$
   $$\text{Stock}_{\text{after uncheck}} = \text{Stock}_{\text{initial}}$$
