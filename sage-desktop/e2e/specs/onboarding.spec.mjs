/**
 * Phase 4.6: Onboarding wizard smoke via tauri-driver.
 *
 * Navigates to /onboarding and asserts the wizard form inputs render.
 * We do NOT submit — generating a real solution spins up the LLM
 * gateway and writes to disk, which is out of scope for smoke.
 */
import { expect } from "@wdio/globals";

describe("Onboarding page", () => {
  before(async () => {
    const link = await $('a[href="/onboarding"]');
    await link.click();
  });

  it("renders the Onboarding heading", async () => {
    const body = await $("body");
    await expect(body).toHaveText(/onboarding|new solution/i);
  });

  it("shows a description textarea", async () => {
    const textarea = await $("textarea");
    await expect(textarea).toBeDisplayed();
  });

  it("shows a solution-name input", async () => {
    const input = await $("input[type='text']");
    await expect(input).toBeDisplayed();
  });
});
