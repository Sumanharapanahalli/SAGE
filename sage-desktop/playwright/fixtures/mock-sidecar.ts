/**
 * Phase 4.7: Tauri invoke() bridge mock for Playwright.
 *
 * Intercepts `@tauri-apps/api/core` imports via `page.addInitScript`
 * so the React UI can render in a vanilla Chromium context — no
 * Tauri window, no packaged .exe, no Python sidecar. Every canned
 * response represents the minimal shape each page needs to render a
 * deterministic empty-state (or small-sample) screenshot.
 *
 * Keep the responses tiny. Anything that changes visually — timestamps,
 * ordering, random IDs — must be stable across runs or the diff will
 * fail on the *second* run.
 */
import type { Page } from "@playwright/test";

export type InvokeResponses = Record<string, unknown>;

const DEFAULT_RESPONSES: InvokeResponses = {
  // Status / header
  handshake: {
    sidecar_version: "0.1.0",
    solution_name: "starter",
    solution_path: "/mock/solutions/starter",
    warnings: [],
  },
  get_status: {
    health: "ok",
    sidecar_version: "0.1.0",
    project: { name: "starter", path: "/mock/solutions/starter" },
    llm: { provider: "gemini", model: "gemini-2.5-flash" },
    pending_approvals: 0,
  },
  get_queue_status: {
    pending: 0,
    in_progress: 0,
    done: 0,
    failed: 0,
    blocked: 0,
    parallel_enabled: false,
    max_workers: 0,
  },
  list_solutions: [
    { name: "starter", path: "/mock/solutions/starter", current: true },
  ],
  get_current_solution: {
    name: "starter",
    path: "/mock/solutions/starter",
  },
  get_llm_info: { provider: "gemini", model: "gemini-2.5-flash" },

  // Approvals
  list_pending_approvals: [],

  // Agents
  list_agents: [],

  // Audit
  list_audit_events: { total: 0, limit: 50, offset: 0, events: [] },
  audit_stats: { total: 0, by_action_type: {} },

  // Builds
  list_builds: [],

  // YAML
  read_yaml: {
    solution: "starter",
    file: "project.yaml",
    content: "name: starter\nversion: 0.1.0\n",
    mtime: 0,
  },

  // Backlog
  list_feature_requests: { solution: [], sage: [] },

  // Updates + telemetry (bypass network)
  check_update: { kind: "up_to_date", current_version: "0.1.0" },
  telemetry_get_status: {
    enabled: false,
    anon_id: null,
    allowed_events: [],
    allowed_fields: [],
  },
};

/**
 * Install the mock on a Playwright `page` before any app code runs.
 * Must be called before `page.goto(...)` or the first render will
 * race against the un-mocked `invoke()`.
 */
export async function installSidecarMock(
  page: Page,
  overrides: InvokeResponses = {},
) {
  const merged = { ...DEFAULT_RESPONSES, ...overrides };
  await page.addInitScript((responses) => {
    // Patch window.__TAURI_INTERNALS__ so `@tauri-apps/api/core.invoke`
    // returns canned data. The real Tauri runtime assigns this object
    // before any app code runs; we mirror that contract.
    (window as unknown as { __TAURI_INTERNALS__: unknown }).__TAURI_INTERNALS__ = {
      invoke: (cmd: string) => {
        const canned = (responses as Record<string, unknown>)[cmd];
        if (canned === undefined) {
          return Promise.reject(
            new Error(`mock-sidecar: no canned response for ${cmd}`),
          );
        }
        return Promise.resolve(canned);
      },
    };
  }, merged as unknown as Record<string, unknown>);
}
