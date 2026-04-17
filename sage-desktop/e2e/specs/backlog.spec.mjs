/**
 * Phase 4.6: Product Backlog page smoke via tauri-driver.
 *
 * Navigates to /backlog and asserts the two-scope tab control renders
 * (solution vs framework — the hard boundary CLAUDE.md enforces).
 */
import { expect } from "@wdio/globals";

describe("Backlog page", () => {
  before(async () => {
    const link = await $('a[href="/backlog"]');
    await link.click();
  });

  it("renders the Backlog heading", async () => {
    const body = await $("body");
    await expect(body).toHaveText(/backlog|feature requests/i);
  });

  it("shows both solution and framework scope tabs", async () => {
    const body = await $("body");
    const text = await body.getText();
    expect(text).toMatch(/solution/i);
    expect(text).toMatch(/sage|framework/i);
  });
});
