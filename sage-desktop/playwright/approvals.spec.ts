import { expect, test } from "@playwright/test";
import { installSidecarMock } from "./fixtures/mock-sidecar";

test.describe("Approvals — visual regression", () => {
  test("empty state renders the zero-approval message", async ({ page }) => {
    await installSidecarMock(page);
    await page.goto("/approvals");
    await expect(page.locator("body")).toContainText(/approval/i, {
      timeout: 5_000,
    });
    await expect(page).toHaveScreenshot("approvals-empty.png");
  });
});
