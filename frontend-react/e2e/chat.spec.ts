import { test, expect } from '@playwright/test';

// Helper to set up authenticated state with mocked APIs
async function setupAuthenticatedUser(page: import('@playwright/test').Page) {
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
      body: JSON.stringify([]),
    });
  });

  await page.route('**/api/jobs', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  // Navigate first, set token, then reload so mocks intercept the auth check
  await page.goto('/');
  await page.evaluate(() => {
    localStorage.setItem('ligant_token', 'fake-jwt-token');
  });
  await page.reload();

  // Wait for main layout to confirm we're authenticated
  await expect(page.getByText('Start a conversation')).toBeVisible({ timeout: 10000 });
}

// The send button is an icon button next to the textarea
function getSendButton(page: import('@playwright/test').Page) {
  return page.locator('button').filter({ has: page.locator('svg') }).last();
}

test.describe('Chat Flow', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthenticatedUser(page);
  });

  test('shows empty state with prompt', async ({ page }) => {
    await expect(page.getByText('Start a conversation')).toBeVisible();
    await expect(page.getByPlaceholder(/ask about protein design/i)).toBeVisible();
  });

  test('can type a message in the input', async ({ page }) => {
    const input = page.getByPlaceholder(/ask about protein design/i);
    await input.fill('Analyze PDB 1ABC');
    await expect(input).toHaveValue('Analyze PDB 1ABC');
  });

  test('send button is disabled when input is empty', async ({ page }) => {
    const sendButton = getSendButton(page);
    await expect(sendButton).toBeDisabled();
  });

  test('sends message and shows SSE response', async ({ page }) => {
    // Mock the chat message endpoint with SSE response
    await page.route('**/api/chat/message', async (route) => {
      const sseBody = [
        'event: text\ndata: "Hello! "\n\n',
        'event: text\ndata: "I can help you "\n\n',
        'event: text\ndata: "design proteins."\n\n',
        'event: done\ndata: {"model_used":"claude-sonnet-4-6"}\n\n',
      ].join('');

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: sseBody,
      });
    });

    const input = page.getByPlaceholder(/ask about protein design/i);
    await input.fill('Help me design a binder');

    const sendButton = getSendButton(page);
    await sendButton.click();

    // User message should appear
    await expect(page.getByText('Help me design a binder')).toBeVisible({ timeout: 5000 });

    // Assistant response should appear (streamed)
    await expect(page.getByText(/I can help you design proteins/)).toBeVisible({ timeout: 5000 });
  });

  test('shows tool call in message', async ({ page }) => {
    await page.route('**/api/chat/message', async (route) => {
      const sseBody = [
        'event: tool_call\ndata: {"name":"fetch_pdb","input":{"pdb_id":"1ABC"}}\n\n',
        'event: tool_result\ndata: {"name":"fetch_pdb","result":"PDB 1ABC fetched successfully"}\n\n',
        'event: text\ndata: "I fetched PDB 1ABC for you."\n\n',
        'event: done\ndata: {"model_used":"claude-sonnet-4-6"}\n\n',
      ].join('');

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: sseBody,
      });
    });

    const input = page.getByPlaceholder(/ask about protein design/i);
    await input.fill('Fetch PDB 1ABC');
    await getSendButton(page).click();

    // Tool call should be visible
    await expect(page.getByText('fetch_pdb')).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/I fetched PDB 1ABC/)).toBeVisible({ timeout: 5000 });
  });

  test('input is disabled while streaming', async ({ page }) => {
    // Use a delayed response to keep streaming state active
    await page.route('**/api/chat/message', async (route) => {
      await new Promise((r) => setTimeout(r, 2000));
      const sseBody = 'event: text\ndata: "Done"\n\nevent: done\ndata: {"model_used":"claude-sonnet-4-6"}\n\n';
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: sseBody,
      });
    });

    const input = page.getByPlaceholder(/ask about protein design/i);
    await input.fill('Test message');
    await getSendButton(page).click();

    // Send button should be disabled during streaming
    await expect(getSendButton(page)).toBeDisabled({ timeout: 2000 });
  });
});
