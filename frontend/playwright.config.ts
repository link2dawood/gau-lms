import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests run against the real stack — Nginx in front of Next.js and
 * Django, with PostgreSQL, Redis and Meilisearch behind them — not against a
 * mocked backend. A Canvas launch depends on cookie attributes, proxy headers
 * and redirects that only exist when the whole chain is present, so a suite
 * that stubbed the API would pass while launches failed.
 *
 * There is deliberately no `webServer` block: the stack is started by Docker
 * Compose and this config attaches to it. `PLAYWRIGHT_BASE_URL` points at the
 * Nginx entry point — `http://nginx` when running inside the compose network,
 * `http://localhost:8080` from the host.
 *
 * Browsers come from the official pinned image (DECISIONS.md D-017), so local
 * runs and CI exercise identical binaries.
 */

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:8080';
const isCI = process.env.CI === 'true' || process.env.CI === '1';

export default defineConfig({
  testDir: './tests/e2e',
  // The reader is not a single-page app; most assertions wait on a server
  // render, so a short default would produce flakes rather than signal.
  timeout: 30_000,
  expect: { timeout: 10_000 },

  fullyParallel: true,
  // A test that only passes on a retry is a broken test. Locally there are no
  // retries, so flakiness is visible immediately instead of being absorbed.
  retries: isCI ? 2 : 0,
  // Spread rather than `workers: isCI ? 2 : undefined`: under
  // exactOptionalPropertyTypes an explicit `undefined` is not the same as an
  // absent key, and Playwright's own types reject it. Omitting the key is what
  // actually means "use the default".
  ...(isCI ? { workers: 2 } : {}),
  forbidOnly: isCI,

  reporter: isCI
    ? [['github'], ['html', { open: 'never' }]]
    : [['list'], ['html', { open: 'never' }]],

  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },

  projects: [
    {
      name: 'desktop-chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      // Responsive behaviour across desktop, tablet and mobile is a Phase 1
      // acceptance criterion, so mobile is a first-class target from the start
      // rather than a pass added at the end. Tablet is added in task 2.14.
      name: 'mobile-chromium',
      use: { ...devices['Pixel 7'] },
    },
  ],
});
