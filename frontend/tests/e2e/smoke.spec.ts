import { expect, test } from '@playwright/test';

/**
 * Smoke test for the deployed stack.
 *
 * Proves the chain is wired end to end: the browser reaches Nginx, Nginx routes
 * page requests to Next.js and API requests to Django, and a server-rendered
 * page reflects data fetched from Django over the internal network.
 *
 * Deliberately small. It exists to show the harness works and the plumbing
 * holds; the acceptance-criteria suite is built in tasks 2.15, 3.16 and 4.7.
 */

test.describe('platform smoke', () => {
  test('the status page server-renders live data from Django', async ({ page }) => {
    const response = await page.goto('/');
    expect(response?.status()).toBe(200);

    await expect(page.getByRole('heading', { name: 'GAU Interactive Textbook' })).toBeVisible();

    // The checks are not in the markup unless the server render reached Django
    // and the response satisfied the response guard.
    const checks = page.getByRole('region').or(page.locator('section')).first();
    await expect(checks).toContainText('database');
    await expect(checks).toContainText('cache');
    await expect(checks).toContainText('available');
  });

  test('Nginx routes API requests to Django, not to Next.js', async ({ request }) => {
    const response = await request.get('/api/health/');

    expect(response.status()).toBe(200);
    expect(response.headers()['content-type']).toContain('application/json');

    const body: unknown = await response.json();
    expect(body).toMatchObject({
      status: 'ok',
      checks: { database: 'ok', cache: 'ok' },
    });
  });

  test('an unknown path is handled by Next.js, not proxied to Django', async ({ page }) => {
    const response = await page.goto('/no-such-page');

    expect(response?.status()).toBe(404);
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
  });

  test('the page is usable at mobile width without horizontal scrolling', async ({ page }) => {
    await page.goto('/');

    // Horizontal overflow is the most common responsive defect and the easiest
    // to regress, so it is asserted from the first test rather than at task 4.6.
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    );
    expect(overflows).toBe(false);
  });
});
