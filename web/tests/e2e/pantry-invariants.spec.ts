import { test, expect } from './fixtures/test-env';

test.describe('US3: Pantry Inventory Invariants & Cook Deduction Verification', () => {
  test.beforeEach(async ({ resetTestData }) => {
    resetTestData();
  });

  test('Pantry lifecycle: barcode intake/manual addition and quantity edits', async ({
    authedPage,
    testUser,
  }) => {
    const authHeaders = { Authorization: `Bearer ${testUser.token}` };

    // 1. Add pantry item via API
    const createRes = await authedPage.request.post('/api/v1/pantry/items', {
      headers: authHeaders,
      data: {
        name: 'Lentilles corail',
        quantity: 500,
        unit: 'g',
        category: 'Épicerie',
      },
    });
    expect(createRes.ok()).toBe(true);
    const item = await createRes.json();
    expect(item.quantity).toBe(500);

    // 2. View in web browser under Garde-manger tab
    await authedPage.goto('/groceries');
    await authedPage.waitForLoadState('domcontentloaded');

    const pantryTab = authedPage.locator('button:has-text("Garde-manger")').first();
    await expect(pantryTab).toBeVisible({ timeout: 10000 });
    await pantryTab.click();

    // Verify item is visible with its initial stock
    await expect(authedPage.locator('text=Lentilles corail').first()).toBeVisible({ timeout: 10000 });
    await expect(authedPage.locator('text=500').first()).toBeVisible();

    // 3. Edit quantity via API and verify browser updates
    const updateRes = await authedPage.request.patch(`/api/v1/pantry/items/${item.id}`, {
      headers: authHeaders,
      data: {
        quantity: 650,
      },
    });
    expect(updateRes.ok()).toBe(true);

    await authedPage.reload();
    await authedPage.locator('button:has-text("Garde-manger")').first().click();
    await expect(authedPage.locator('text=650').first()).toBeVisible();
  });

  test('Cook confirmation & unconfirmation: strict mathematical stock conservation', async ({
    authedPage,
    testUser,
    auditStore,
  }) => {
    const authHeaders = { Authorization: `Bearer ${testUser.token}` };

    // 1. Seed initial pantry item with 500 g of Lentilles corail
    const pantryRes = await authedPage.request.post('/api/v1/pantry/items', {
      headers: authHeaders,
      data: {
        name: 'Lentilles corail',
        quantity: 500,
        unit: 'g',
        category: 'Épicerie',
      },
    });
    expect(pantryRes.ok()).toBe(true);
    const pantryItem = await pantryRes.json();

    // 2. Locate cloned Dahl recipe (needs 150 g of lentilles corail)
    const recRes = await authedPage.request.get('/api/v1/recipes', { headers: authHeaders });
    const recipes = await recRes.json();
    const dahlRecipe = recipes.find((r: any) => r.name.includes('Dahl'));
    expect(dahlRecipe).toBeDefined();

    // 3. Cook confirmation: deduct 150 g -> stock should be exactly 350 g
    const cookRes = await authedPage.request.post(`/api/v1/recipes/${dahlRecipe.id}/confirm-cooked`, {
      headers: authHeaders,
      data: { note: 'E2E test cooking' },
    });
    expect(cookRes.ok()).toBe(true);

    const checkPantryRes1 = await authedPage.request.get('/api/v1/pantry/items', { headers: authHeaders });
    const pantryItems1 = await checkPantryRes1.json();
    const itemAfterCook = pantryItems1.find((p: any) => p.id === pantryItem.id);
    expect(itemAfterCook.quantity).toBe(350);

    // 4. Cook unconfirmation: restore 150 g -> stock strictly recovers to 500 g
    const uncookRes = await authedPage.request.post(`/api/v1/recipes/${dahlRecipe.id}/unconfirm-cooked`, {
      headers: authHeaders,
    });
    expect(uncookRes.ok()).toBe(true);

    const checkPantryRes2 = await authedPage.request.get('/api/v1/pantry/items', { headers: authHeaders });
    const pantryItems2 = await checkPantryRes2.json();
    const itemAfterUncook = pantryItems2.find((p: any) => p.id === pantryItem.id);
    expect(itemAfterUncook.quantity).toBe(500);

    // Record invariant audit
    auditStore.recordInvariant({
      item: 'Lentilles corail',
      action: 'confirm_cooked (150g) -> unconfirm_cooked',
      initialStock: '500 g',
      afterActionStock: `${itemAfterCook.quantity} g`,
      revertedStock: `${itemAfterUncook.quantity} g`,
      isPreserved: itemAfterUncook.quantity === 500,
    });
  });

  test('Grocery check/uncheck invariant: stock transitions without drift', async ({
    authedPage,
    testUser,
    auditStore,
  }) => {
    const authHeaders = { Authorization: `Bearer ${testUser.token}` };

    // 1. Create a grocery item: Pâtes penne (500 g)
    const grocRes = await authedPage.request.post('/api/v1/groceries', {
      headers: authHeaders,
      data: {
        name: 'Pâtes penne',
        quantity: 500,
        unit: 'g',
        category: 'Épicerie',
      },
    });
    expect(grocRes.ok()).toBe(true);
    const groceryItem = await grocRes.json();

    // Initial pantry check for Penne
    const p1 = await authedPage.request.get('/api/v1/pantry/items', { headers: authHeaders });
    const p1Items = await p1.json();
    const initialPenne = p1Items.find((p: any) => p.name.toLowerCase().includes('penne'));
    const initialQty = initialPenne ? initialPenne.quantity : 0;

    // 2. Check the grocery item
    const checkRes = await authedPage.request.patch(`/api/v1/groceries/${groceryItem.id}`, {
      headers: authHeaders,
      data: { checked: true },
    });
    expect(checkRes.ok()).toBe(true);

    // Pantry should now reflect +500g
    const p2 = await authedPage.request.get('/api/v1/pantry/items', { headers: authHeaders });
    const p2Items = await p2.json();
    const checkedPenne = p2Items.find((p: any) => p.name.toLowerCase().includes('penne'));
    const afterQty = checkedPenne ? checkedPenne.quantity : 0;
    expect(afterQty).toBe(initialQty + 500);

    // 3. Uncheck the grocery item
    const uncheckRes = await authedPage.request.patch(`/api/v1/groceries/${groceryItem.id}`, {
      headers: authHeaders,
      data: { checked: false },
    });
    expect(uncheckRes.ok()).toBe(true);

    const p3 = await authedPage.request.get('/api/v1/pantry/items', { headers: authHeaders });
    const p3Items = await p3.json();
    const revertedPenne = p3Items.find((p: any) => p.name.toLowerCase().includes('penne'));
    const revertedQty = revertedPenne ? revertedPenne.quantity : 0;
    expect(revertedQty).toBe(initialQty);

    // Record invariant audit
    auditStore.recordInvariant({
      item: 'Pâtes penne',
      action: 'grocery_check (+500g) -> grocery_uncheck',
      initialStock: `${initialQty} g`,
      afterActionStock: `${afterQty} g`,
      revertedStock: `${revertedQty} g`,
      isPreserved: revertedQty === initialQty,
    });
  });
});
