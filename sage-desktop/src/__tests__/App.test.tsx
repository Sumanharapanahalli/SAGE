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
  getCurrentSolution: vi
    .fn()
    .mockResolvedValue({ name: "starter", path: "/solutions/starter" }),
  switchSolution: vi.fn(),
  onboardingGenerate: vi.fn(),
  startBuild: vi.fn(),
  listBuilds: vi.fn().mockResolvedValue([]),
  getBuild: vi.fn(),
  approveBuildStage: vi.fn(),
  readYaml: vi.fn().mockResolvedValue({
    file: "project",
    solution: "demo",
    content: "",
    path: "",
  }),
  writeYaml: vi.fn(),
}));

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn().mockResolvedValue(() => {}),
}));

import * as client from "@/api/client";
import { App, queryClient } from "@/App";

describe("App routing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // App's QueryClient is a module-level singleton — clear cached data
    // (e.g. current-solution, staleTime: Infinity) so each test's mock
    // scenario actually takes effect instead of reusing a prior render's
    // cached result.
    queryClient.clear();
  });

  it("redirects / to /approvals when a solution is already active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "starter",
      path: "/solutions/starter",
    });
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/approvals/i),
    );
  });

  it("redirects / to /home when no solution is active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/solutions/i),
    );
  });

  it("redirects a solution-scoped route to /home when no solution is active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    render(
      <MemoryRouter initialEntries={["/audit"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/solutions/i),
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

  it("renders the Builds route", async () => {
    render(
      <MemoryRouter initialEntries={["/builds"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        /builds/i,
      ),
    );
  });

  it("renders Home without redirecting away when a solution is already active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "starter",
      path: "/solutions/starter",
    });
    render(
      <MemoryRouter initialEntries={["/home"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole("heading")).toHaveTextContent(/solutions/i),
    );
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByRole("heading")).toHaveTextContent(/solutions/i);
  });

  it("renders Onboarding without a solution loaded", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    render(
      <MemoryRouter initialEntries={["/onboarding"]}>
        <App />
      </MemoryRouter>,
    );
    // Onboarding.tsx has its own in-page <h2>, alongside Header's <h1> — both
    // read "New solution", so disambiguate with level (same pattern as the
    // Builds route test above).
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { level: 1 }),
      ).toHaveTextContent(/new solution/i),
    );
  });
});
