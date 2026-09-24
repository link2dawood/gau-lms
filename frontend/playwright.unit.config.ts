import { defineConfig } from '@playwright/test';

/**
 * Unit tests for pure functions — no browser, no stack, no Docker.
 *
 * Separate from `playwright.config.ts` on purpose. That suite attaches to a
 * running Docker Compose stack by design (D-017) and cannot run without one;
 * these test functions that take a value and return a value, so they should
 * run anywhere, in a second, including on a machine where Docker is paused.
 * Mixing them would have made the cheap tests as expensive as the dear ones.
 *
 * This adds no dependency: `@playwright/test` is already the pinned runner
 * (D-017), and Section B's fixed stack is untouched.
 */
export default defineConfig({
  testDir: './tests/unit',
  fullyParallel: true,
  forbidOnly: process.env.CI === 'true' || process.env.CI === '1',
  // No retries anywhere. A pure function that passes on the second attempt is
  // not flaky, it is wrong — and D-019's reason for retrying in CI, an
  // infrastructure hiccup, cannot apply to a test that touches nothing.
  retries: 0,
  reporter: [['list']],
});
