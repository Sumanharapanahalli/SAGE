/**
 * Phase 4.6: Agents page smoke via tauri-driver.
 *
 * Asserts the roster page loads and at least one core role name is
 * visible (Analyst, Developer, Monitor, Planner, Universal).
 */
import { expect } from "@wdio/globals";

describe("Agents page", () => {
  before(async () => {
    const link = await $('a[href="/agents"]');
    await link.click();
  });

  it("renders the Agents heading", async () => {
    const body = await $("body");
    await expect(body).toHaveText(/agents/i);
  });

  it("shows at least one core role", async () => {
    const body = await $("body");
    const text = await body.getText();
    expect(text).toMatch(/analyst|developer|monitor|planner|universal/i);
  });
});
