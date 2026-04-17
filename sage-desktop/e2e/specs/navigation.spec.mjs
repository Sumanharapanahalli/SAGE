/**
 * Phase 4.6: full page navigation exercise.
 *
 * Boots the packaged SAGE Desktop .exe via tauri-driver, walks through
 * every primary page, and asserts landmark content renders.
 */
import { expect } from "@wdio/globals";

const PAGES = [
  { href: "/approvals", heading: /approvals/i },
  { href: "/agents", heading: /agents/i },
  { href: "/audit", heading: /audit/i },
  { href: "/status", heading: /status/i },
  { href: "/backlog", heading: /backlog|feature requests/i },
  { href: "/builds", heading: /builds/i },
  { href: "/onboarding", heading: /onboarding|new solution/i },
  { href: "/settings", heading: /settings|active solution/i },
];

describe("SAGE Desktop navigation", () => {
  for (const page of PAGES) {
    it(`loads ${page.href}`, async () => {
      const link = await $(`a[href="${page.href}"]`);
      await link.click();
      const body = await $("body");
      const text = await body.getText();
      expect(text).toMatch(page.heading);
    });
  }
});
