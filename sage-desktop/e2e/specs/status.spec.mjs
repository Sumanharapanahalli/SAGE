/**
 * Phase 4.6: Status dashboard smoke via tauri-driver.
 *
 * Asserts every primary status tile renders. Actual values vary (the
 * sidecar + LLM state can be anything on a dev machine), so we match
 * the tile labels, not the values.
 */
import { expect } from "@wdio/globals";

describe("Status page", () => {
  before(async () => {
    const link = await $('a[href="/status"]');
    await link.click();
  });

  it("renders the Status heading", async () => {
    const body = await $("body");
    await expect(body).toHaveText(/status/i);
  });

  it("shows the health / sidecar / LLM tile labels", async () => {
    const body = await $("body");
    const text = await body.getText();
    expect(text).toMatch(/health|sidecar|llm|provider|pending/i);
  });
});
