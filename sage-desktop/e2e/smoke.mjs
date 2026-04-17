#!/usr/bin/env node
/**
 * sage-desktop end-to-end smoke test.
 *
 * Phase 1 deferral: a true tauri-driver-based E2E test requires the
 * packaged .exe and Edge WebView2 on the runner. Until the Phase 4
 * packaging work, this target invokes the Python sidecar directly and
 * round-trips a handshake + list_pending_approvals, which is the same
 * wire contract the Rust side drives in production.
 *
 * Exit 0 on success, non-zero on any failure.
 */
import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { once } from "node:events";

const sageRoot = resolve(process.cwd(), "..");
const desktopDir = process.cwd();
const python = process.env.SAGE_PYTHON || (process.platform === "win32" ? "python" : "python3");

function send(proc, request) {
  proc.stdin.write(JSON.stringify(request) + "\n");
}

function onLine(proc, cb) {
  let buf = "";
  proc.stdout.setEncoding("utf8");
  proc.stdout.on("data", (chunk) => {
    buf += chunk;
    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (line) cb(line);
    }
  });
}

function run() {
  return new Promise((resolvePromise, rejectPromise) => {
    const proc = spawn(python, ["-u", "-m", "sidecar"], {
      cwd: desktopDir,
      env: { ...process.env, SAGE_ROOT: sageRoot, PYTHONUNBUFFERED: "1" },
      stdio: ["pipe", "pipe", "inherit"],
    });
    proc.on("error", rejectPromise);

    const expected = { handshake: false, list_pending_approvals: false };
    onLine(proc, (line) => {
      try {
        const resp = JSON.parse(line);
        if (resp.id === "e2e-1" && resp.result) expected.handshake = true;
        if (resp.id === "e2e-2" && (resp.result || resp.error)) expected.list_pending_approvals = true;
        if (expected.handshake && expected.list_pending_approvals) {
          proc.kill("SIGTERM");
          resolvePromise();
        }
      } catch (e) {
        rejectPromise(new Error(`bad NDJSON line: ${line}`));
      }
    });

    send(proc, { jsonrpc: "2.0", id: "e2e-1", method: "handshake", params: {} });
    send(proc, {
      jsonrpc: "2.0",
      id: "e2e-2",
      method: "list_pending_approvals",
      params: {},
    });

    setTimeout(() => {
      proc.kill("SIGTERM");
      rejectPromise(new Error("e2e smoke timeout"));
    }, 10_000);
  });
}

run()
  .then(() => {
    console.log("sage-desktop e2e smoke: OK (handshake + list_pending_approvals round-tripped)");
    process.exit(0);
  })
  .catch((err) => {
    console.error("sage-desktop e2e smoke FAILED:", err.message ?? err);
    process.exit(1);
  });
