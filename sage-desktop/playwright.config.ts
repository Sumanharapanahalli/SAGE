/**
 * Phase 4.7: Playwright visual regression for sage-desktop.
 *
 * Runs the Vite dev server (no Tauri shell — just the React UI in a
 * real Chromium) and snapshots four canonical pages: Approvals, Builds,
 * Audit, and YAML. Every test mocks the Tauri invoke() bridge via
 * window-level stubs so the UI renders deterministic data without a
 * real sidecar.
 *
 * Usage:
 *   npm run test:visual           # run against existing snapshots
 *   npm run test:visual:update    # regenerate on intentional UI change
 */
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./playwright",
  timeout: 30_000,
  expect: {
    // Pixel diff tolerance. 0.2% accommodates font-rendering jitter
    // between macOS/Linux CI runners without masking real drift.
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.002,
      animations: "disabled",
      caret: "hide",
    },
  },
  fullyParallel: true,
  reporter: [["list"]],
  snapshotDir: "playwright/snapshots",
  // Each project/screenshot filename gets an -OS suffix that changes
  // per platform, so committed snapshots stay OS-agnostic when
  // regenerated on the same CI runner (ubuntu-latest).
  snapshotPathTemplate:
    "{snapshotDir}/{testFilePath}/{arg}{ext}",
  use: {
    baseURL: "http://localhost:1420",
    trace: "on-first-retry",
    viewport: { width: 1280, height: 800 },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    port: 1420,
    timeout: 60_000,
    reuseExistingServer: !process.env.CI,
  },
});
