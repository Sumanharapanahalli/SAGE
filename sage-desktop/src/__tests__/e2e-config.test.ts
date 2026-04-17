/**
 * Unit test that guards the tauri-driver E2E scaffolding. We don't run
 * the actual WebDriver session here — that needs the packaged .exe and
 * a running tauri-driver process. Instead we verify the config + spec
 * files exist and reference the correct paths, so drift is caught at
 * `npm run test` time rather than at release time.
 */
// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference types="node" />
import { readFileSync, statSync } from "fs";
import { resolve } from "path";
import { describe, expect, it } from "vitest";

const e2eRoot = resolve(process.cwd(), "e2e");

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

  it("per-page smoke specs exist for all 8 primary pages", () => {
    for (const name of [
      "approvals",
      "agents",
      "audit",
      "status",
      "builds",
      "yaml",
      "onboarding",
      "backlog",
    ]) {
      const spec = resolve(e2eRoot, "specs", `${name}.spec.mjs`);
      expect(statSync(spec).isFile()).toBe(true);
      const src = readFileSync(spec, "utf-8");
      expect(src).toContain(`a[href="/${name}"]`);
    }
  });
});

describe("Phase 4.7 Playwright visual regression", () => {
  const pwRoot = resolve(process.cwd(), "playwright");

  it("playwright.config.ts exists and targets the Vite dev server", () => {
    const cfg = resolve(process.cwd(), "playwright.config.ts");
    expect(statSync(cfg).isFile()).toBe(true);
    const src = readFileSync(cfg, "utf-8");
    expect(src).toContain("baseURL");
    expect(src).toContain("localhost:1420");
  });

  it("mock-sidecar fixture covers the invoke() bridge", () => {
    const src = readFileSync(
      resolve(pwRoot, "fixtures", "mock-sidecar.ts"),
      "utf-8",
    );
    expect(src).toContain("__TAURI_INTERNALS__");
    expect(src).toContain("installSidecarMock");
  });

  it("has pixel-diff specs for the 4 canonical pages", () => {
    for (const name of ["approvals", "builds", "audit", "yaml"]) {
      const spec = resolve(pwRoot, `${name}.spec.ts`);
      expect(statSync(spec).isFile()).toBe(true);
      const src = readFileSync(spec, "utf-8");
      expect(src).toContain("toHaveScreenshot");
      expect(src).toContain(`/${name}`);
    }
  });
});
