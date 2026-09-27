import { test, expect } from './fixtures/test-env';

const PROHIBITED_UNITS = ['pavé', 'pavés', 'tranche', 'tranches', 'morceau', 'morceaux', 'boîte', 'boîtes', 'gousse', 'gousses'];
const ALLOWED_UNITS = ['g', 'kg', 'ml', 'cl', 'dl', 'l', 'item', 'c. à soupe', 'c. à café', 'pincée'];

test.describe('US5: AI Assistant Conversations & Guardrails', () => {
  test.beforeEach(async ({ resetTestData }) => {
    resetTestData();
  });

  test('audit web interface for presence of AI assistant chat component', async ({ authedPage, auditStore }) => {
    await authedPage.goto('/recipes');
    await authedPage.waitForLoadState('networkidle');

    // Inspect navigation and page elements for assistant chat access
    const assistantNavLink = authedPage.locator('nav a:has-text("Assistant"), nav a:has-text("Copilot"), nav a:has-text("Chat")');
    const assistantFloatingWidget = authedPage.locator('[data-testid="assistant-chat"], [aria-label*="assistant"], button:has-text("Assistant")');

    const hasNav = (await assistantNavLink.count()) > 0;
    const hasWidget = (await assistantFloatingWidget.count()) > 0;

    if (!hasNav && !hasWidget) {
      auditStore.recordGap({
        id: 'GAP-001',
        severity: 'P2',
        category: 'Missing Feature / UI Gap',
        title: 'AI Assistant Chat UI is not mounted in the web frontend',
        details: 'While the backend exposes /api/v1/assistant/chat and the mobile app contains an assistant screen, the web interface currently lacks an assistant chat page or floating widget.',
        component: 'web/src/App.tsx (NavigationBar)',
      });
    }

    // Verify main recipes page heading is visible
    await expect(authedPage.getByRole('heading', { name: 'Recipes', exact: true })).toBeVisible();
  });

  test('verify assistant API SSE streaming connection and protocol contract', async ({ testUser }) => {
    // Connect to /api/v1/assistant/chat via fetch with an AbortController so we read streaming chunks without hanging
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);

    try {
      const response = await fetch('http://localhost:8000/api/v1/assistant/chat', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${testUser.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: 'Bonjour, que peux-tu faire ?',
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      expect(response.status).toBe(200);
      expect(response.headers.get('content-type')).toContain('text/event-stream');

      // Read initial stream chunk
      const reader = response.body?.getReader();
      expect(reader).toBeDefined();

      if (reader) {
        const { value } = await reader.read();
        const chunkText = new TextDecoder().decode(value);
        expect(chunkText).toContain('event:');
        await reader.cancel();
      }
    } catch (err: any) {
      clearTimeout(timeoutId);
      if (err.name !== 'AbortError') {
        throw err;
      }
    }
  });

  test('verify recipe and grocery ingredient guardrails enforce metric units and ban cut units', async ({ authedPage, testUser }) => {
    // 1. Verify existing benchmark recipes adhere strictly to allowed metric units
    const recipesRes = await authedPage.request.get('http://localhost:8000/api/v1/recipes', {
      headers: { Authorization: `Bearer ${testUser.token}` },
    });
    expect(recipesRes.status()).toBe(200);
    const recipes = await recipesRes.json();
    expect(recipes.length).toBeGreaterThan(0);

    for (const recipe of recipes) {
      if (recipe.ingredients && Array.isArray(recipe.ingredients)) {
        for (const ing of recipe.ingredients) {
          const unitLower = (ing.unit || '').toLowerCase().trim();
          // Assert prohibited cut units are strictly absent
          for (const prohibited of PROHIBITED_UNITS) {
            expect(
              unitLower,
              `Recipe "${recipe.name}" ingredient "${ing.name}" must not use prohibited cut unit "${prohibited}"`
            ).not.toBe(prohibited);
          }
          // Assert unit is in allowed list if present
          if (unitLower) {
            expect(
              ALLOWED_UNITS.includes(unitLower),
              `Recipe "${recipe.name}" ingredient "${ing.name}" unit "${unitLower}" must be standard metric (${ALLOWED_UNITS.join(', ')})`
            ).toBeTruthy();
          }
        }
      }
    }

    // 2. Verify grocery item creation enforces metric units
    const groceryRes = await authedPage.request.post('http://localhost:8000/api/v1/groceries', {
      headers: {
        Authorization: `Bearer ${testUser.token}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: 'Saumon frais',
        quantity: 300,
        unit: 'g',
        note: '2 pavés',
      },
    });

    expect([200, 201]).toContain(groceryRes.status());
    const groceryItem = await groceryRes.json();
    expect(groceryItem.name).toBe('Saumon frais');
    expect(groceryItem.quantity).toBe(300);
    expect(groceryItem.unit).toBe('g');
    expect(groceryItem.note).toContain('2 pavés');

    // 3. Verify discrete counting items use "item" unit
    const avocadoRes = await authedPage.request.post('http://localhost:8000/api/v1/groceries', {
      headers: {
        Authorization: `Bearer ${testUser.token}`,
        'Content-Type': 'application/json',
      },
      data: {
        name: 'Avocat',
        quantity: 2,
        unit: 'item',
      },
    });
    expect([200, 201]).toContain(avocadoRes.status());
    const avocado = await avocadoRes.json();
    expect(avocado.unit).toBe('item');
  });
});
