import { test, expect } from '@playwright/test';

test.describe('Authentication', () => {
  test.beforeEach(async ({ page }) => {
    // Clear any stored tokens
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());
    await page.reload();
  });

  test('shows login form by default', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Ligant.ai')).toBeVisible();
    // Use the submit button specifically (inside the form)
    await expect(page.locator('form').getByRole('button', { name: 'Sign In' })).toBeVisible();
    await expect(page.getByLabel('Email')).toBeVisible();
    await expect(page.getByLabel('Password')).toBeVisible();
  });

  test('can switch to register form', async ({ page }) => {
    await page.goto('/');
    // Click the tab (not the submit button)
    await page.getByRole('button', { name: 'Create Account' }).first().click();
    await expect(page.getByLabel('Display Name')).toBeVisible();
    await expect(page.getByLabel('Confirm Password')).toBeVisible();
  });

  test('shows validation error for mismatched passwords', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: 'Create Account' }).first().click();
    await page.getByLabel('Display Name').fill('Test User');
    await page.getByLabel(/^Email$/).fill('test@example.com');
    await page.getByLabel(/^Password$/).fill('password123');
    await page.getByLabel('Confirm Password').fill('different');
    // Click the submit button inside the form
    await page.locator('form').getByRole('button', { name: /create account/i }).click();
    await expect(page.getByText(/passwords do not match/i)).toBeVisible();
  });

  test('shows error on invalid login', async ({ page }) => {
    await page.goto('/');

    // Mock the API to return 401
    await page.route('**/api/auth/login', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid email or password' }),
      });
    });

    await page.getByLabel('Email').fill('bad@example.com');
    await page.getByLabel('Password').fill('wrongpass');
    await page.locator('form').getByRole('button', { name: /sign in/i }).click();

    await expect(page.getByText(/invalid email or password/i)).toBeVisible();
  });

  test('successful login shows main app', async ({ page }) => {
    await page.goto('/');

    // Mock login API
    await page.route('**/api/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          token: 'fake-jwt-token',
          user_id: 'user-123',
          email: 'test@example.com',
          display_name: 'Test User',
        }),
      });
    });

    // Mock /me endpoint for auth check
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 'user-123',
          email: 'test@example.com',
          display_name: 'Test User',
          is_admin: false,
          created_at: '2025-01-01T00:00:00Z',
        }),
      });
    });

    // Mock conversations
    await page.route('**/api/chat/conversations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    // Mock jobs
    await page.route('**/api/jobs', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password123');
    await page.locator('form').getByRole('button', { name: /sign in/i }).click();

    // Should see the main layout
    await expect(page.getByText('Start a conversation')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('Sign Out')).toBeVisible();
  });
});
