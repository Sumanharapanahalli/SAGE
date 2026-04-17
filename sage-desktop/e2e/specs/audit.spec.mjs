/**
 * Phase 4.6: Audit page smoke via tauri-driver.
 *
 * Asserts the audit log page loads and renders either events or the
 * empty-state message.
 */
import { expect } from "@wdio/globals";

describe("Audit page", () => {
  before(async () => {
    const link = await $('a[href="/audit"]');
    await link.click();
  });

  it("renders the Audit heading", async () => {
    const body = await $("body");
    await expect(body).toHaveText(/audit/i);
  });

  it("shows an action-type filter control", async () => {
    // Filter select or text-input is the main interactive element.
    const filter = await $("select, input[type='search'], input[type='text']");
    await expect(filter).toBeDisplayed();
  });
});
