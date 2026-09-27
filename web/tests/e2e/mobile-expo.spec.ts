import { test, expect } from '@playwright/test';

const MOBILE_BASE_URL = process.env.EXPO_URL || 'http://localhost:8081';

test.use({
  viewport: { width: 390, height: 844 },
  userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
  isMobile: true,
  hasTouch: true,
  baseURL: MOBILE_BASE_URL,
});

test.describe('Expo Mobile SaaS Application E2E Tests', () => {
  test('1. Mobile Login Flow: authenticate on Expo mobile screen', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    // Verify mobile header
    await expect(page.getByText('AdamHUB SaaS')).toBeVisible();
    await expect(page.getByText('Connexion')).toBeVisible();

    // Fill credentials
    const emailInput = page.locator('input[placeholder*="exemple"], input[type="email"]').first();
    const passwordInput = page.locator('input[placeholder*="••"], input[type="password"]').first();

    await emailInput.fill('e2e-tester@adamelhirch.com');
    await passwordInput.fill('TestPassword123!');

    // Click "Se connecter"
    await page.getByText('Se connecter').click();

    // Wait for bottom navigation tab to appear
    await expect(page.getByRole('tab', { name: /Cuisine/i })).toBeVisible({ timeout: 10000 });
  });

  test('2. Mobile Kitchen: browse recipes, drive cart & shopping list', async ({ page }) => {
    // Authenticate via token injection
    await page.addInitScript(() => {
      localStorage.setItem(
        'adamhub_saas_token',
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZW1haWwiOiJlMmUtdGVzdGVyQGFkYW1lbGhpcmNoLmNvbSIsImRpc3BsYXlfbmFtZSI6IkUyRSBUZXN0ZXIiLCJpYXQiOjE3ODk3NTA4MjcsImV4cCI6MTc5MjM0MjgyN30.tt8Cj3TxFGuxLqk29D12buGwvqJvdvVI4cOQJMIxx0I'
      );
    });

    await page.goto('/kitchen');
    await page.waitForLoadState('networkidle');

    // Verify main screen title
    await expect(page.getByText('Cuisine & Repas')).toBeVisible();

    // Check shopping list tab and active drive cart
    await expect(page.getByText('Courses').first()).toBeVisible();
    await expect(page.getByText(/Panier Drive actif/i).first()).toBeVisible();

    // Switch to Recipes tab
    await page.getByTestId('kitchen-tab-recipes').click();
    await page.waitForTimeout(800);

    // Assert canonical recipes exist
    await expect(page.getByText('Dahl de lentilles corail (Marmiton)')).toBeVisible();
    await expect(page.getByText('Pâtes crémeuses au saumon')).toBeVisible();

    // Check Stock tab
    await page.getByTestId('kitchen-tab-pantry').click();
    await page.waitForTimeout(800);
    await expect(page.getByText(/Articles en réserve|Garde-manger|Rechercher/).first()).toBeVisible();
  });

  test('3. Mobile AI Copilot: open assistant screen, inspect suggestions & chat bar', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem(
        'adamhub_saas_token',
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZW1haWwiOiJlMmUtdGVzdGVyQGFkYW1lbGhpcmNoLmNvbSIsImRpc3BsYXlfbmFtZSI6IkUyRSBUZXN0ZXIiLCJpYXQiOjE3ODk3NTA4MjcsImV4cCI6MTc5MjM0MjgyN30.tt8Cj3TxFGuxLqk29D12buGwvqJvdvVI4cOQJMIxx0I'
      );
    });

    await page.goto('/assistant');
    await page.waitForLoadState('networkidle');

    // Verify Assistant Header
    await expect(page.getByText('AdamHUB Copilot').first()).toBeVisible();
    await expect(page.getByText('Assistant IA contextuel')).toBeVisible();

    // Verify Welcome message
    await expect(page.getByText(/Bonjour ! Je suis ton copilote AdamHUB/)).toBeVisible();

    // Verify Quick suggestion pills
    await expect(page.getByText('Repas conseillé pour ce midi ?')).toBeVisible();
    await expect(page.getByText('Ajoute 6 œufs, du lait et du riz aux courses')).toBeVisible();

    // Check text input field
    const chatInput = page.locator('input[placeholder*="Demande une recette"], textarea[placeholder*="Demande une recette"]').first();
    await expect(chatInput).toBeVisible();
    await chatInput.fill('Quels sont mes ingrédients pour le dahl ?');
    await page.waitForTimeout(500);
  });

  test('4. Mobile Bottom Tabs Navigation: switch across all core domains', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem(
        'adamhub_saas_token',
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZW1haWwiOiJlMmUtdGVzdGVyQGFkYW1lbGhpcmNoLmNvbSIsImRpc3BsYXlfbmFtZSI6IkUyRSBUZXN0ZXIiLCJpYXQiOjE3ODk3NTA4MjcsImV4cCI6MTc5MjM0MjgyN30.tt8Cj3TxFGuxLqk29D12buGwvqJvdvVI4cOQJMIxx0I'
      );
    });

    await page.goto('/kitchen');
    await page.waitForLoadState('networkidle');

    // 1. Click "Accueil" tab
    await page.getByRole('tab', { name: /Accueil/i }).click();
    await page.waitForTimeout(800);

    // 2. Click "Finance" tab
    await page.getByRole('tab', { name: /Finance/i }).click();
    await page.waitForTimeout(800);
    await expect(page.getByText(/Budget|Finances|Solde/i).first()).toBeVisible();

    // 3. Click "Sport" tab
    await page.getByRole('tab', { name: /Sport/i }).click();
    await page.waitForTimeout(800);
    await expect(page.getByText(/Fitness|Séances|Exercices|Entraînement/i).first()).toBeVisible();

    // 4. Click "Cuisine" tab
    await page.getByRole('tab', { name: /Cuisine/i }).click();
    await page.waitForTimeout(800);
    await expect(page.getByText('Cuisine & Repas')).toBeVisible();
  });
});

