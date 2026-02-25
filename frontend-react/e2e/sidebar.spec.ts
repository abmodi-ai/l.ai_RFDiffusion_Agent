import { test, expect } from '@playwright/test';

async function setupAuthenticatedUser(
  page: import('@playwright/test').Page,
  conversations: unknown[] = [],
) {
  // Set up route mocks BEFORE navigation
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

  await page.route('**/api/chat/conversations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(conversations),
    });
  });

  await page.route('**/api/jobs', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.goto('/');
  await page.evaluate(() => {
    localStorage.setItem('ligant_token', 'fake-jwt-token');
  });
  await page.reload();
  await expect(page.getByText('Start a conversation')).toBeVisible({ timeout: 10000 });
}

test.describe('Sidebar & Conversations', () => {
  test('shows user info in sidebar', async ({ page }) => {
    await setupAuthenticatedUser(page);
    await expect(page.getByText('Test User')).toBeVisible();
    await expect(page.getByText('test@example.com')).toBeVisible();
  });

  test('new conversation button resets chat', async ({ page }) => {
    await setupAuthenticatedUser(page);
    const newBtn = page.getByRole('button', { name: /new conversation/i });
    await expect(newBtn).toBeVisible();
    await newBtn.click();
    await expect(page.getByText('Start a conversation')).toBeVisible();
  });

  test('displays conversation list with titles', async ({ page }) => {
    const conversations = [
      {
        conversation_id: 'conv-1',
        title: 'Protein Binder Design',
        preview: 'Help me design a binder for IL-6',
        updated_at: '2025-06-01T12:00:00Z',
        message_count: 5,
      },
      {
        conversation_id: 'conv-2',
        title: null,
        preview: 'What is RFdiffusion?',
        updated_at: '2025-06-01T11:00:00Z',
        message_count: 2,
      },
    ];

    await setupAuthenticatedUser(page, conversations);

    // Use exact match to avoid matching the subtitle "Ask about protein binder design..."
    await expect(page.getByText('Protein Binder Design', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('What is RFdiffusion?', { exact: true })).toBeVisible();
  });

  test('can switch between conversations and jobs tabs', async ({ page }) => {
    await setupAuthenticatedUser(page);

    // Tab text is "Conversations" and "Jobs (0)"
    const jobsTab = page.getByRole('button', { name: /jobs/i });
    await jobsTab.click();

    // Should show "No jobs yet"
    await expect(page.getByText('No jobs yet')).toBeVisible();

    // Switch back to conversations
    const chatsTab = page.getByRole('button', { name: /conversations/i });
    await chatsTab.click();

    // Should show "No conversations yet"
    await expect(page.getByText('No conversations yet')).toBeVisible();
  });

  test('sign out clears auth and shows login', async ({ page }) => {
    await page.route('**/api/auth/logout', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });

    await setupAuthenticatedUser(page);

    const signOutBtn = page.getByText('Sign Out');
    await expect(signOutBtn).toBeVisible();
    await signOutBtn.click();

    // Should show login form
    await expect(page.getByText('Ligant.ai')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('form').getByRole('button', { name: /sign in/i })).toBeVisible({ timeout: 5000 });
  });
});
