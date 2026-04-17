import { expect, test } from "@playwright/test";
import { installSidecarMock } from "./fixtures/mock-sidecar";

test.describe("YAML editor — visual regression", () => {
  test("default project.yaml loads without edits", async ({ page }) => {
    await installSidecarMock(page);
    await page.goto("/yaml");
    await expect(page.locator("body")).toContainText(/yaml/i, {
      timeout: 5_000,
    });
    await expect(page).toHaveScreenshot("yaml-default.png");
  });
});
