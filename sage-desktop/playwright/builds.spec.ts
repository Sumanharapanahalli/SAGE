import { expect, test } from "@playwright/test";
import { installSidecarMock } from "./fixtures/mock-sidecar";

test.describe("Builds — visual regression", () => {
  test("empty state renders the no-builds message", async ({ page }) => {
    await installSidecarMock(page);
    await page.goto("/builds");
    await expect(page.locator("body")).toContainText(/build/i, {
      timeout: 5_000,
    });
    await expect(page).toHaveScreenshot("builds-empty.png");
  });
});
