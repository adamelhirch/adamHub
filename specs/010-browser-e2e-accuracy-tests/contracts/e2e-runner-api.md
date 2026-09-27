# Contract: E2E Browser Runner & CLI Commands

**Feature**: `010-browser-e2e-accuracy-tests`  
**Date**: 2026-09-18  

---

## 1. CLI Commands (`web/package.json`)

The browser automation test suite exposes standardized NPM scripts in `web/package.json`:

```bash
# 1. Full E2E Test Suite (headless)
npm run test:e2e

# 2. Visual / Headed Mode (opens a visible browser on screen)
npm run test:e2e:headed

# 3. Interactive Playwright UI Mode (visual test explorer, timeline, DOM inspect)
npm run test:e2e:ui

# 4. Smoke Test Suite (fast critical path sanity check < 2 min)
npm run test:e2e:smoke

# 5. Accuracy & Benchmark Suite (comprehensive retail matching & inventory checks)
npm run test:e2e:accuracy
```

---

## 2. Root Launcher Script (`scripts/run_e2e_tests.sh`)

A top-level shell script orchestrates environment checks and test execution:

```bash
./scripts/run_e2e_tests.sh [OPTIONS]

Options:
  --headed          Launch visible browser window for observation
  --ui              Open Playwright interactive UI runner
  --smoke           Run only rapid smoke tests (< 2 minutes)
  --accuracy        Run deep retail accuracy and inventory benchmarks
  --report          Open the generated HTML/Markdown accuracy report after completion
  --help            Show usage information
```

### Exit Codes
- `0`: All tests passed, accuracy benchmark = 100%, zero fatal defects.
- `1`: One or more test assertions failed, or accuracy benchmark < 100%.
- `2`: Infrastructure failure (backend service unreachable or port collision).

---

## 3. Test Fixture Contract (`web/tests/e2e/fixtures/test-env.ts`)

Playwright test specifications import pre-configured fixtures providing:

```typescript
import { test as base, expect } from '@playwright/test';

interface AdamHubTestFixtures {
  // Pre-authenticated page context with test tenant session
  authedPage: Page;
  // Test tenant user credentials and metadata
  testUser: {
    id: number;
    email: string;
    token: string;
  };
  // Helper to reset test tenant data between runs
  resetTestData: () => Promise<void>;
}
```

---

## 4. Benchmark Spec Contract (`web/tests/e2e/benchmarks/accuracy-cases.ts`)

```typescript
export interface BenchmarkAssertion {
  ingredientName: string;
  expectedKeywords: string[];
  prohibitedKeywords: string[];
  maxExpectedPriceEuros?: number;
}

export interface BenchmarkCase {
  recipeName: string;
  servings: number;
  store: 'carrefour' | 'intermarche' | 'leclerc' | 'auchan';
  strategy: 'budget' | 'mdd' | 'bio';
  assertions: BenchmarkAssertion[];
}
```
