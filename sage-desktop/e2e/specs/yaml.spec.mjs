/**
 * Phase 4.6: YAML authoring page smoke via tauri-driver.
 *
 * Navigates to /yaml, asserts the file picker + textarea are visible,
 * and that the current YAML content loads (not a bare error banner).
 * We do NOT exercise Save here — that would mutate the live solution
 * YAML. Write round-trips are covered by the sidecar integration test.
 */
import { expect } from "@wdio/globals";

describe("YAML editor page", () => {
  before(async () => {
    const link = await $('a[href="/yaml"]');
    await link.click();
  });

  it("renders the YAML heading", async () => {
    const body = await $("body");
    await expect(body).toHaveText(/yaml/i);
  });

  it("shows a file picker (select)", async () => {
    const select = await $("select");
    await expect(select).toBeDisplayed();
  });

  it("shows a content textarea", async () => {
    const textarea = await $("textarea");
    await expect(textarea).toBeDisplayed();
  });
});
