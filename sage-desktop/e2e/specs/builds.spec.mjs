/**
 * Phase 4.6: Builds (Build Console) smoke via tauri-driver.
 *
 * Navigates to /builds and asserts both the runs table region and the
 * "Start a new build" form render. We do NOT start a real build here
 * — that would spin up the BuildOrchestrator + LLM calls, which is
 * out of scope for a smoke suite.
 */
import { expect } from "@wdio/globals";

describe("Builds page", () => {
  before(async () => {
    const link = await $('a[href="/builds"]');
    await link.click();
  });

  it("renders the Builds heading", async () => {
    const body = await $("body");
    await expect(body).toHaveText(/builds/i);
  });

  it("shows the start-build form with a description textarea", async () => {
    const textarea = await $('textarea');
    await expect(textarea).toBeDisplayed();
  });

  it("shows either a runs table or an empty-state message", async () => {
    const body = await $("body");
    const text = await body.getText();
    expect(text).toMatch(/runs|no builds|start a build|start a new build/i);
  });
});
