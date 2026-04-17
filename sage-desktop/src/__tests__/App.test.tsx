import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listPendingApprovals: vi.fn().mockResolvedValue([]),
  getApproval: vi.fn(),
  approveProposal: vi.fn(),
  rejectProposal: vi.fn(),
  batchApprove: vi.fn(),
  listAuditEvents: vi
    .fn()
    .mockResolvedValue({ total: 0, limit: 50, offset: 0, events: [] }),
  getAuditByTrace: vi.fn(),
  auditStats: vi.fn(),
  listAgents: vi.fn().mockResolvedValue([]),
  getAgent: vi.fn(),
  getStatus: vi.fn().mockResolvedValue({
    health: "ok",
    sidecar_version: "0.1.0",
    project: null,
    llm: null,
    pending_approvals: 0,
  }),
  handshake: vi.fn(),
  toDesktopError: (e: unknown) => e,
  getLlmInfo: vi.fn().mockResolvedValue({
    provider_name: "GeminiCLIProvider",
    model: "gemini-2.0",
    available_providers: ["gemini"],
  }),
  switchLlm: vi.fn(),
  listFeatureRequests: vi.fn().mockResolvedValue([]),
  submitFeatureRequest: vi.fn(),
  updateFeatureRequest: vi.fn(),
  getQueueStatus: vi.fn().mockResolvedValue({
    pending: 0, in_progress: 0, done: 0, failed: 0, blocked: 0,
    parallel_enabled: false, max_workers: 0,
  }),
  listQueueTasks: vi.fn().mockResolvedValue([]),
  listSolutions: vi.fn().mockResolvedValue([]),
  getCurrentSolution: vi.fn().mockResolvedValue(null),
  switchSolution: vi.fn(),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn().mockResolvedValue(() => {}),
}));

import { App } from "@/App";

describe("App routing", () => {
  beforeEach(() => vi.clearAllMocks());

  it("redirects / to /approvals", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/approvals/i),
    );
  });

  it("renders the Audit route", async () => {
    render(
      <MemoryRouter initialEntries={["/audit"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/audit/i),
    );
  });

  it("renders the Status route", async () => {
    render(
      <MemoryRouter initialEntries={["/status"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/status/i),
    );
  });
});
