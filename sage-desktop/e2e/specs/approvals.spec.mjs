/**
 * Phase 4.6: Approvals page smoke via tauri-driver.
 *
 * Walks to /approvals and asserts the page renders landmark text.
 * The page uses real sidecar data; on a fresh solution the pending
 * list is typically empty so we just assert the empty-state copy or
 * a list container is present — not a specific proposal.
 */
import { expect } from "@wdio/globals";

describe("Approvals page", () => {
  before(async () => {
    const link = await $('a[href="/approvals"]');
    await link.click();
  });

  it("renders the Approvals heading", async () => {
    const body = await $("body");
    await expect(body).toHaveText(/approvals/i);
  });

  it("shows either a pending list or an empty-state message", async () => {
    const body = await $("body");
    const text = await body.getText();
    const listOrEmpty =
      /pending|no proposals|nothing to review|all caught up/i.test(text);
    expect(listOrEmpty).toBe(true);
  });
});
