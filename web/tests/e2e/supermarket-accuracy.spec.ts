import { test, expect } from './fixtures/test-env';
import { CANONICAL_BENCHMARKS } from './benchmarks/accuracy-cases';

test.describe('US2: Supermarket Matching & Culinary Accuracy Audit', () => {
  test.beforeEach(async ({ resetTestData }) => {
    resetTestData();
  });

  test('Dahl de lentilles corail: Recipe-to-Cart end-to-end audit with 0% absurd matches', async ({
    authedPage,
    auditStore,
  }) => {
    // 1. Navigate to Recipes and locate the canonical benchmark recipe card
    await authedPage.goto('/recipes');
    await authedPage.waitForLoadState('domcontentloaded');

    const recipeHeading = authedPage.locator('h2:has-text("Dahl de lentilles corail (Marmiton)")').first();
    await expect(recipeHeading).toBeVisible({ timeout: 10000 });

    const cardContainer = authedPage.locator('div').filter({ has: recipeHeading }).filter({ hasText: 'Courses' }).last();

    // 2. Add recipe ingredients to groceries via the Courses button, waiting for the 200 response
    const addCoursesBtn = cardContainer.getByRole('button', { name: 'Courses' });
    await expect(addCoursesBtn).toBeVisible();

    const [addResponse] = await Promise.all([
      authedPage.waitForResponse((res) => res.url().includes('/add-to-groceries') && res.status() === 200),
      addCoursesBtn.click(),
    ]);
    expect(addResponse.ok()).toBe(true);

    // 3. Navigate to Groceries page
    await authedPage.goto('/groceries');
    await authedPage.waitForLoadState('domcontentloaded');

    // Verify key items present in list
    await expect(authedPage.locator('text=Lentilles corail').first()).toBeVisible({ timeout: 10000 });
    await expect(authedPage.locator('text=Lait de coco').first()).toBeVisible();
    await expect(authedPage.locator('text=Ail').first()).toBeVisible();

    // Select Carrefour store chip on toolbar
    const carrefourBtn = authedPage.locator('button:has-text("Carrefour")').first();
    await expect(carrefourBtn).toBeVisible({ timeout: 10000 });
    await carrefourBtn.click();
    await authedPage.waitForTimeout(300);

    // 4. Trigger Drive staging and capture the backend response
    const prepareDriveBtn = authedPage.locator('button:has-text("Préparer mon Drive")').first();
    await expect(prepareDriveBtn).toBeVisible();

    const [jobResponse] = await Promise.all([
      authedPage.waitForResponse((res) => res.url().includes('/supermarket/cart/jobs') && res.status() === 201),
      prepareDriveBtn.click(),
    ]);
    expect(jobResponse.ok()).toBe(true);
    const jobData = await jobResponse.json();

    // 5. Assert CartReviewPanel appears
    const reviewModal = authedPage.locator('h2:has-text("Panier Drive")').first();
    await expect(reviewModal).toBeVisible({ timeout: 15000 });

    // 6. Audit matched products against canonical accuracy benchmarks
    const dahlBenchmark = CANONICAL_BENCHMARKS.find((b) => b.id === 'dahl-lentilles-corail-carrefour-budget')!;

    for (const rule of dahlBenchmark.assertions) {
      // Find the specific item matched for this ingredient
      const matchedItem = jobData.items.find((it: any) => {
        const name = (it.name || '').toLowerCase();
        return rule.expectedKeywords.some((kw) => name.includes(kw.toLowerCase()));
      });

      const isExpectedFound = !!matchedItem;
      const itemName = (matchedItem?.name || '').toLowerCase();

      // Check negative assertions (prohibited items) on this specific matched item
      const violatedProhibitions = rule.prohibitedKeywords.filter((badKw) => {
        const regex = new RegExp(`\\b${badKw}\\b`, 'i');
        return regex.test(itemName);
      });

      const isAccurate = isExpectedFound && violatedProhibitions.length === 0;

      auditStore.recordBenchmark({
        benchmarkId: dahlBenchmark.id,
        recipeName: dahlBenchmark.recipeName,
        store: jobData.store,
        strategy: jobData.optimization_strategy,
        ingredient: rule.ingredientName,
        matchedProduct: matchedItem ? matchedItem.name : 'Missing/Unmatched',
        priceText: matchedItem ? `${(matchedItem.unit_price_cents / 100).toFixed(2)} €` : undefined,
        isAccurate,
        reason: violatedProhibitions.length > 0
          ? `Absurd match detected: contained [${violatedProhibitions.join(', ')}]`
          : rule.reason,
      });

      expect(violatedProhibitions, `Prohibited items found for ${rule.ingredientName}: ${violatedProhibitions.join(', ')}`).toEqual([]);
      expect(isExpectedFound, `Expected authentic keyword for ${rule.ingredientName} not found`).toBe(true);
    }
  });

  test('Optimization Strategy Fidelity: Budget, MDD, and Bio preserve culinary accuracy', async ({
    authedPage,
    testUser,
  }) => {
    const authHeaders = { Authorization: `Bearer ${testUser.token}` };

    // 1. Fetch user recipes
    const addRes = await authedPage.request.get('/api/v1/recipes', { headers: authHeaders });
    expect(addRes.ok()).toBe(true);
    const recipes = await addRes.json();
    const dahlRecipe = recipes.find((r: any) => r.name.includes('Dahl'));
    expect(dahlRecipe).toBeDefined();

    // 2. Add to groceries
    const groceryRes = await authedPage.request.post(`/api/v1/recipes/${dahlRecipe.id}/add-to-groceries`, {
      headers: authHeaders,
      data: {},
    });
    expect(groceryRes.ok()).toBe(true);

    // 3. Test strategies: budget, mdd, bio
    const strategies = ['budget', 'mdd', 'bio'] as const;

    for (const strategy of strategies) {
      const jobRes = await authedPage.request.post('/api/v1/supermarket/cart/jobs', {
        headers: authHeaders,
        data: {
          store: 'carrefour',
          optimization_strategy: strategy,
        },
      });

      expect(jobRes.ok()).toBe(true);
      const job = await jobRes.json();
      expect(job.items.length).toBeGreaterThan(0);

      // Verify no absurd matches across any item
      for (const item of job.items) {
        const itemName = (item.name || '').toLowerCase();
        // Zero poultry for garlic
        if (itemName.includes('ail') || item.grocery_item_id) {
          if (itemName.includes('ail')) {
            expect(itemName).not.toContain('volaille');
            expect(itemName).not.toContain('poulet');
          }
        }
        // Zero butter for salt
        if (itemName.includes('sel')) {
          expect(itemName).not.toContain('beurre');
        }
        // Zero cow milk for coconut milk
        if (itemName.includes('coco')) {
          expect(itemName).toContain('coco');
          expect(itemName).not.toContain('vache');
        }
        // Zero vegan slices for lentils
        if (itemName.includes('lentille')) {
          expect(itemName).not.toContain('tranche');
          expect(itemName).not.toContain('fleury');
          expect(itemName).not.toContain('salade');
        }
      }
    }
  });
});
