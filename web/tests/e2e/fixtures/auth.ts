import { Page, request } from '@playwright/test';

export const E2E_USER = {
  email: 'e2e-tester@adamelhirch.com',
  password: 'TestPassword123!',
  displayName: 'E2E Tester',
};

let cachedToken: string | null = null;
let cachedUserId: number | null = null;

/**
 * Fetch JWT token for the E2E test tenant, registering the user if needed.
 */
export async function getE2EAuthToken(apiBaseUrl: string = 'http://localhost:8000'): Promise<{ token: string; userId: number }> {
  if (cachedToken && cachedUserId) {
    return { token: cachedToken, userId: cachedUserId };
  }

  const reqContext = await request.newContext();

  try {
    const loginRes = await reqContext.post(`${apiBaseUrl}/api/v1/auth/login`, {
      data: { email: E2E_USER.email, password: E2E_USER.password },
    });

    if (loginRes.ok()) {
      const data = await loginRes.json();
      cachedToken = data.token;
      cachedUserId = data.user.id;
      return { token: cachedToken!, userId: cachedUserId! };
    }

    // Attempt register if login failed
    const registerRes = await reqContext.post(`${apiBaseUrl}/api/v1/auth/register`, {
      data: {
        email: E2E_USER.email,
        password: E2E_USER.password,
        display_name: E2E_USER.displayName,
      },
    });

    if (registerRes.ok()) {
      const data = await registerRes.json();
      cachedToken = data.token;
      cachedUserId = data.user.id;
      return { token: cachedToken!, userId: cachedUserId! };
    }

    throw new Error(`Failed to authenticate E2E user: ${loginRes.status()} / ${registerRes.status()}`);
  } finally {
    await reqContext.dispose();
  }
}

/**
 * Injects the JWT token directly into page localStorage before any page navigation.
 */
export async function authenticatePage(page: Page, token: string): Promise<void> {
  await page.addInitScript((authToken) => {
    window.localStorage.setItem('adamhub_token', authToken);
  }, token);
}

/**
 * Performs end-to-end UI login via the /login form.
 */
export async function loginViaUi(
  page: Page,
  email: string = E2E_USER.email,
  password: string = E2E_USER.password
): Promise<void> {
  await page.goto('/login');
  await page.waitForLoadState('domcontentloaded');

  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button[type="submit"]');

  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 10000 });
}
