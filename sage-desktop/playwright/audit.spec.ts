import { expect, test } from "@playwright/test";
import { installSidecarMock } from "./fixtures/mock-sidecar";

test.describe("Audit — visual regression", () => {
  test("empty state renders the zero-events message", async ({ page }) => {
    await installSidecarMock(page);
    await page.goto("/audit");
    await expect(page.locator("body")).toContainText(/audit/i, {
      timeout: 5_000,
    });
    await expect(page).toHaveScreenshot("audit-empty.png");
  });
});
