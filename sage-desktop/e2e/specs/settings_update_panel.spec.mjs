/**
 * Phase 4.6: verify the auto-update panel added in Task 4.4 mounts
 * and the "Check for updates" button is reachable.
 */
import { expect } from "@wdio/globals";

describe("Settings → Application updates", () => {
  it("renders the update panel with a check button", async () => {
    const settingsLink = await $('a[href="/settings"]');
    await settingsLink.click();

    const heading = await $("h2*=Application updates");
    await heading.waitForDisplayed({ timeout: 5_000 });

    const button = await $("button*=Check for updates");
    await expect(button).toBeDisplayed();
    await expect(button).toBeEnabled();
  });
});
