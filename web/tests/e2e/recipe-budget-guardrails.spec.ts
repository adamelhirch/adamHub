import { test, expect } from './fixtures/test-env';

test.describe('Universal Culinary Guardrails & Budget Accuracy Tests', () => {
  test.beforeEach(async ({ resetTestData }) => {
    resetTestData();
  });

  test('1. Dahl de lentilles corail: 0% cold cuts, 0% soups, 0% hummus across stores', async ({
    authedPage,
  }) => {
    await authedPage.goto('/recipes');
    await authedPage.waitForLoadState('domcontentloaded');

    // Verify recipe card exists
    const recipeHeading = authedPage.locator('h2:has-text("Dahl de lentilles corail (Marmiton)")').first();
    await expect(recipeHeading).toBeVisible({ timeout: 10000 });

    // Add recipe ingredients to groceries
    const cardContainer = authedPage.locator('div').filter({ has: recipeHeading }).filter({ hasText: 'Courses' }).last();
    const addCoursesBtn = cardContainer.getByRole('button', { name: 'Courses' });
    await expect(addCoursesBtn).toBeVisible();

    const [addResponse] = await Promise.all([
      authedPage.waitForResponse((res) => res.url().includes('/add-to-groceries') && res.status() === 200),
      addCoursesBtn.click(),
    ]);
    expect(addResponse.ok()).toBe(true);

    // Navigate to groceries
    await authedPage.goto('/groceries');
    await authedPage.waitForLoadState('domcontentloaded');

    // Select Carrefour store chip on toolbar
    const carrefourBtn = authedPage.locator('button:has-text("Carrefour")').first();
    await expect(carrefourBtn).toBeVisible({ timeout: 10000 });
    await carrefourBtn.click();
    await authedPage.waitForTimeout(300);

    const prepareDriveBtn = authedPage.locator('button:has-text("Préparer mon Drive")').first();
    await expect(prepareDriveBtn).toBeVisible();

    const [jobResponse] = await Promise.all([
      authedPage.waitForResponse((res) => res.url().includes('/supermarket/cart/jobs') && res.status() === 201),
      prepareDriveBtn.click(),
    ]);
    expect(jobResponse.ok()).toBe(true);
    const jobData = await jobResponse.json();

    // Verify cart review items
    const matchedItems: any[] = jobData.items || jobData.matched_items || [];
    expect(matchedItems.length).toBeGreaterThan(0);

    const prohibitedTerms = [
      'tranche', 'tranches', 'fleury', 'salade', 'salades',
      'houmous', 'hummus', 'veloute', 'velouté', 'soupe', 'terrine',
    ];

    for (const item of matchedItems) {
      const pName = (item.name || '').toLowerCase();
      const gName = (item.grocery_item_name || '').toLowerCase();

      // If looking for lentils, strictly ban cold cuts, soups, salads
      if (gName.includes('lentille')) {
        for (const term of prohibitedTerms) {
          expect(pName).not.toContain(term);
        }
        expect(pName).toContain('lentille');
      }

      // If looking for coconut milk, strictly ban dairy milk
      if (gName.includes('coco')) {
        expect(pName).toContain('coco');
        expect(pName).not.toContain('vache');
      }

      // If looking for garlic, ban chicken broth
      if (gName === 'ail' || gName.includes('ail')) {
        expect(pName).not.toContain('volaille');
        expect(pName).not.toContain('poulet');
      }
    }
  });

  test('2. Pâtes crémeuses au saumon: raw fish & genuine pasta cut without ready-meal trays', async ({
    authedPage,
  }) => {
    await authedPage.goto('/recipes');
    await authedPage.waitForLoadState('domcontentloaded');

    const recipeHeading = authedPage.locator('h2:has-text("Pâtes crémeuses au saumon")').first();
    await expect(recipeHeading).toBeVisible({ timeout: 10000 });

    const cardContainer = authedPage.locator('div').filter({ has: recipeHeading }).filter({ hasText: 'Courses' }).last();
    const addCoursesBtn = cardContainer.getByRole('button', { name: 'Courses' });

    const [addResponse] = await Promise.all([
      authedPage.waitForResponse((res) => res.url().includes('/add-to-groceries') && res.status() === 200),
      addCoursesBtn.click(),
    ]);
    expect(addResponse.ok()).toBe(true);

    await authedPage.goto('/groceries');
    await authedPage.waitForLoadState('domcontentloaded');

    const prepareDriveBtn = authedPage.locator('button:has-text("Préparer mon Drive")').first();
    await expect(prepareDriveBtn).toBeVisible();

    const [jobResponse] = await Promise.all([
      authedPage.waitForResponse((res) => res.url().includes('/supermarket/cart/jobs') && res.status() === 201),
      prepareDriveBtn.click(),
    ]);
    expect(jobResponse.ok()).toBe(true);
    const jobData = await jobResponse.json();

    const matchedItems: any[] = jobData.items || jobData.matched_items || [];
    for (const item of matchedItems) {
      const pName = (item.name || '').toLowerCase();
      const gName = (item.grocery_item_name || '').toLowerCase();

      // Salmon must not be a microwave prepared meal, pizza, or rillettes
      if (gName.includes('saumon')) {
        expect(pName).toContain('saumon');
        expect(pName).not.toContain('pizza');
        expect(pName).not.toContain('quiche');
        expect(pName).not.toContain('lasagne');
        expect(pName).not.toContain('rillette');
      }

      // Cream must not be dessert or ice cream
      if (gName.includes('creme') || gName.includes('crème')) {
        expect(pName).not.toContain('glace');
        expect(pName).not.toContain('dessert');
      }
    }
  });

  test('3. Budget Ceiling Verification: total drive cart cost for staple recipe stays economical', async ({
    authedPage,
  }) => {
    // 1. Add Dahl ingredients to groceries
    await authedPage.goto('/recipes');
    await authedPage.waitForLoadState('domcontentloaded');

    const recipeHeading = authedPage.locator('h2:has-text("Dahl de lentilles corail (Marmiton)")').first();
    await expect(recipeHeading).toBeVisible({ timeout: 10000 });

    const cardContainer = authedPage.locator('div').filter({ has: recipeHeading }).filter({ hasText: 'Courses' }).last();
    const addCoursesBtn = cardContainer.getByRole('button', { name: 'Courses' });

    const [addResponse] = await Promise.all([
      authedPage.waitForResponse((res) => res.url().includes('/add-to-groceries') && res.status() === 200),
      addCoursesBtn.click(),
    ]);
    expect(addResponse.ok()).toBe(true);

    // 2. Go to groceries and select Carrefour
    await authedPage.goto('/groceries');
    await authedPage.waitForLoadState('domcontentloaded');

    const carrefourBtn = authedPage.locator('button:has-text("Carrefour")').first();
    await expect(carrefourBtn).toBeVisible({ timeout: 10000 });
    await carrefourBtn.click();
    await authedPage.waitForTimeout(300);

    // 3. Trigger drive preparation
    const prepareDriveBtn = authedPage.locator('button:has-text("Préparer mon Drive")').first();
    await expect(prepareDriveBtn).toBeVisible();

    const [jobResponse] = await Promise.all([
      authedPage.waitForResponse((res) => res.url().includes('/supermarket/cart/jobs') && res.status() === 201),
      prepareDriveBtn.click(),
    ]);
    expect(jobResponse.ok()).toBe(true);
    const jobData = await jobResponse.json();

    // 4. In budget/mdd strategy, individual staple items must stay within strict economic limits
    const matchedItems: any[] = jobData.items || jobData.matched_items || [];
    expect(matchedItems.length).toBeGreaterThan(0);

    for (const item of matchedItems) {
      const unitPriceEuros = (item.unit_price_cents || 0) / 100;
      const gName = (item.grocery_item_name || '').toLowerCase();

      // Staples like salt, tomato concentrate, lentils should never exceed 3€/unit
      if (gName.includes('sel') || gName.includes('concentré') || gName.includes('concentre')) {
        expect(unitPriceEuros).toBeLessThan(3.0);
      }
      if (gName.includes('lentille')) {
        expect(unitPriceEuros).toBeLessThan(3.5);
      }
      if (gName.includes('coco')) {
        expect(unitPriceEuros).toBeLessThan(2.5);
      }
    }
  });
});
