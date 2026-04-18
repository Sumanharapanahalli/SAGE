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

    const expected = {
      handshake: false,
      list_pending_approvals: false,
      llm_get_info: false,
      backlog_list: false,
      queue_get_status: false,
      collective_stats: false,
    };
    onLine(proc, (line) => {
      try {
        const resp = JSON.parse(line);
        if (resp.id === "e2e-1" && resp.result) expected.handshake = true;
        if (resp.id === "e2e-2" && (resp.result || resp.error)) expected.list_pending_approvals = true;
        if (resp.id === "e2e-3" && (resp.result || resp.error)) expected.llm_get_info = true;
        if (resp.id === "e2e-4" && (resp.result || resp.error)) expected.backlog_list = true;
        if (resp.id === "e2e-5" && (resp.result || resp.error)) expected.queue_get_status = true;
        if (resp.id === "e2e-6" && (resp.result || resp.error)) {
          // Either a valid stats dict (wired) or a "not wired" error (unwired) counts
          // as a successful roundtrip — both prove the NDJSON event loop dispatched
          // the collective.stats method all the way to the handler.
          if (resp.result) {
            const r = resp.result;
            if (
              typeof r.learning_count !== "number" ||
              typeof r.help_request_count !== "number" ||
              typeof r.git_available !== "boolean" ||
              typeof r.repo_path !== "string"
            ) {
              rejectPromise(new Error(`collective.stats result missing expected keys: ${JSON.stringify(r)}`));
              return;
            }
          } else if (resp.error) {
            const msg = (resp.error.message || "").toLowerCase();
            if (!msg.includes("not wired")) {
              rejectPromise(new Error(`collective.stats unexpected error: ${JSON.stringify(resp.error)}`));
              return;
            }
          }
          expected.collective_stats = true;
        }
        if (Object.values(expected).every(Boolean)) {
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
    send(proc, { jsonrpc: "2.0", id: "e2e-3", method: "llm.get_info", params: {} });
    send(proc, { jsonrpc: "2.0", id: "e2e-4", method: "backlog.list", params: {} });
    send(proc, { jsonrpc: "2.0", id: "e2e-5", method: "queue.get_status", params: {} });
    send(proc, { jsonrpc: "2.0", id: "e2e-6", method: "collective.stats", params: {} });

    setTimeout(() => {
      proc.kill("SIGTERM");
      rejectPromise(new Error("e2e smoke timeout"));
    }, 10_000);
  });
}

run()
  .then(() => {
    console.log("sage-desktop e2e smoke: OK (handshake + list_pending_approvals + llm.get_info + backlog.list + queue.get_status + collective.stats round-tripped)");
    process.exit(0);
  })
  .catch((err) => {
    console.error("sage-desktop e2e smoke FAILED:", err.message ?? err);
    process.exit(1);
  });
