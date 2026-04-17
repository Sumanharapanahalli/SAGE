/**
 * WebdriverIO configuration for tauri-driver E2E tests.
 *
 * Prereqs (documented in .claude/docs/interfaces/desktop-gui.md):
 *   - `cargo install tauri-driver` (listens on 127.0.0.1:4444 by default)
 *   - Microsoft Edge WebView2 runtime (already required by Tauri)
 *   - `npm run build && npm run tauri -- build` has produced the exe
 *
 * Run: `npm run test:e2e:tauri`
 */
import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { existsSync } from "node:fs";

const projectRoot = resolve(import.meta.dirname, "..");
const appBinary = resolve(
  projectRoot,
  "src-tauri/target/release/sage-desktop.exe",
);

if (!existsSync(appBinary)) {
  console.error(
    `Missing Tauri binary at ${appBinary}. Run \`npm run tauri -- build\` first.`,
  );
  process.exit(1);
}

let tauriDriver;

export const config = {
  runner: "local",
  specs: [resolve(import.meta.dirname, "specs", "*.spec.mjs")],
  maxInstances: 1,
  capabilities: [
    {
      "tauri:options": {
        application: appBinary,
      },
      browserName: "wry",
    },
  ],
  hostname: "127.0.0.1",
  port: 4444,
  logLevel: "info",
  framework: "mocha",
  mochaOpts: {
    ui: "bdd",
    timeout: 60_000,
  },
  reporters: ["spec"],
  // Boot tauri-driver once before the test suite; kill it after.
  onPrepare: () => {
    tauriDriver = spawn("tauri-driver", [], {
      stdio: [null, process.stdout, process.stderr],
    });
  },
  onComplete: () => {
    if (tauriDriver) tauriDriver.kill();
  },
};
