/**
 * Phase 4.7: DOM-level visual regression.
 *
 * Full pixel-diff requires a headless browser (Playwright+tauri-driver
 * or a dev server under Chromium). That stack is substantial. In the
 * meantime, serialized DOM structure catches 80% of unintended UI
 * drift — classes, text content, element hierarchy — at vitest speed
 * and with zero extra infra.
 *
 * When the rendered structure genuinely changes, regenerate snapshots
 * with `npx vitest run -u` and review the diff in the PR.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getStatus: vi.fn(),
  handshake: vi.fn(),
  getQueueStatus: vi.fn(),
  listPendingApprovals: vi.fn(),
  listAgents: vi.fn(),
  listAuditEvents: vi.fn(),
  auditStats: vi.fn(),
  getLlmInfo: vi.fn(),
  listSolutions: vi.fn(),
  getCurrentSolution: vi.fn(),
  listFeatureRequests: vi.fn(),
  checkUpdate: vi.fn(),
  installUpdate: vi.fn(),
  listBuilds: vi.fn(),
}));

import * as client from "@/api/client";

function renderWith(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("visual regression (DOM snapshots)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("Status page empty state", async () => {
    vi.mocked(client.getStatus).mockResolvedValue({
      health: "ok",
      sidecar_version: "0.1.0",
      project: null,
      llm: null,
      pending_approvals: 0,
    });
    vi.mocked(client.getQueueStatus).mockResolvedValue({
      pending: 0,
      in_progress: 0,
      done: 0,
      failed: 0,
      blocked: 0,
      parallel_enabled: false,
      max_workers: 0,
    });
    const { Status } = await import("@/pages/Status");
    const { container } = renderWith(<Status />);
    expect(container.firstChild).toMatchSnapshot();
  });

  it("Approvals page empty state", async () => {
    vi.mocked(client.listPendingApprovals).mockResolvedValue([]);
    const { Approvals } = await import("@/pages/Approvals");
    const { container } = renderWith(<Approvals />);
    expect(container.firstChild).toMatchSnapshot();
  });

  it("Audit page empty state", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 0,
      limit: 50,
      offset: 0,
      events: [],
    });
    vi.mocked(client.auditStats).mockResolvedValue({
      total: 0,
      by_action_type: {},
    });
    const { Audit } = await import("@/pages/Audit");
    const { container } = renderWith(<Audit />);
    expect(container.firstChild).toMatchSnapshot();
  });

  it("Agents page empty state", async () => {
    vi.mocked(client.listAgents).mockResolvedValue([]);
    const { Agents } = await import("@/pages/Agents");
    const { container } = renderWith(<Agents />);
    expect(container.firstChild).toMatchSnapshot();
  });
});
