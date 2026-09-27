import { test, expect } from './fixtures/test-env';
import { loginViaUi, E2E_USER } from './fixtures/auth';

test.describe('US1: Visual & Interactive Smoke Navigation', () => {
  test.beforeEach(async ({ resetTestData }) => {
    resetTestData();
  });

  test('Sanity check: full application navigation (< 2 min)', async ({ authedPage, auditStore }) => {
    // 1. Calendar / Dashboard
    await authedPage.goto('/');
    await authedPage.waitForLoadState('domcontentloaded');
    await expect(authedPage).toHaveURL(/\/$/);
    await expect(authedPage.locator('text=AdamHUB').first()).toBeVisible();

    // 2. Tasks
    await authedPage.goto('/tasks');
    await authedPage.waitForLoadState('domcontentloaded');
    await expect(authedPage).toHaveURL(/\/tasks/);

    // 3. Finances
    await authedPage.goto('/finances');
    await authedPage.waitForLoadState('domcontentloaded');
    await expect(authedPage).toHaveURL(/\/finances/);

    // 4. Recipes
    await authedPage.goto('/recipes');
    await authedPage.waitForLoadState('domcontentloaded');
    await expect(authedPage).toHaveURL(/\/recipes/);
    await expect(authedPage.locator('text=Dahl de lentilles corail (Marmiton)').first()).toBeVisible({ timeout: 10000 });

    // 5. Groceries & Tabs (Courses, Garde-manger, Panier)
    await authedPage.goto('/groceries');
    await authedPage.waitForLoadState('domcontentloaded');
    await expect(authedPage).toHaveURL(/\/groceries/);

    // Switch to Garde-manger (Pantry) tab
    const pantryTab = authedPage.locator('button:has-text("Garde-manger")').first();
    if (await pantryTab.isVisible()) {
      await pantryTab.click();
      await authedPage.waitForTimeout(300);
    }

    // Switch to Panier tab
    const cartTab = authedPage.locator('button:has-text("Panier")').first();
    if (await cartTab.isVisible()) {
      await cartTab.click();
      await authedPage.waitForTimeout(300);
    }

    // 6. Fitness
    await authedPage.goto('/fitness');
    await authedPage.waitForLoadState('domcontentloaded');
    await expect(authedPage).toHaveURL(/\/fitness/);

    // 7. Check for Assistant UI presence
    const assistantTrigger = authedPage.locator('button:has-text("Assistant"), [aria-label*="assistant" i]');
    const assistantCount = await assistantTrigger.count();
    if (assistantCount === 0) {
      auditStore.recordAnomaly({
        anomalyId: 'GAP-001',
        severity: 'P2',
        category: 'UI/UX',
        title: 'Assistant Chat UI Not Mounted',
        details: 'The backend provides /api/v1/assistant/chat but the frontend web app does not currently expose a floating widget or dedicated page for the AI assistant.',
        reproductionJourney: 'Smoke test navigation',
      });
    }
  });

  test('UI Login Flow: authenticates via login form', async ({ page }) => {
    await loginViaUi(page, E2E_USER.email, E2E_USER.password);
    await expect(page).not.toHaveURL(/\/login/);
    await expect(page.locator('text=AdamHUB').first()).toBeVisible();
  });
});
