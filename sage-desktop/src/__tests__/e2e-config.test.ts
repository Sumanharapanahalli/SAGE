/**
 * Unit test that guards the tauri-driver E2E scaffolding. We don't run
 * the actual WebDriver session here — that needs the packaged .exe and
 * a running tauri-driver process. Instead we verify the config + spec
 * files exist and reference the correct paths, so drift is caught at
 * `npm run test` time rather than at release time.
 */
import { readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const e2eRoot = resolve(__dirname, "..", "..", "e2e");

describe("tauri-driver E2E scaffolding", () => {
  it("tauri-driver.config.mjs exists", () => {
    const cfg = resolve(e2eRoot, "tauri-driver.config.mjs");
    expect(statSync(cfg).isFile()).toBe(true);
    const src = readFileSync(cfg, "utf-8");
    expect(src).toContain("tauri:options");
    expect(src).toContain("port: 4444");
    expect(src).toContain("sage-desktop.exe");
  });

  it("navigation spec references every primary route", () => {
    const spec = readFileSync(
      resolve(e2eRoot, "specs", "navigation.spec.mjs"),
      "utf-8",
    );
    for (const route of [
      "/approvals",
      "/agents",
      "/audit",
      "/status",
      "/backlog",
      "/builds",
      "/onboarding",
      "/settings",
    ]) {
      expect(spec).toContain(`"${route}"`);
    }
  });

  it("update-panel spec covers the Task 4.4 UI", () => {
    const spec = readFileSync(
      resolve(e2eRoot, "specs", "settings_update_panel.spec.mjs"),
      "utf-8",
    );
    expect(spec).toContain("Application updates");
    expect(spec).toContain("Check for updates");
  });
});
