import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getCurrentSolution: vi
    .fn()
    .mockResolvedValue({ name: "starter", path: "/solutions/starter" }),
  listPendingApprovals: vi.fn().mockResolvedValue([]),
}));

import * as client from "@/api/client";
import { Sidebar } from "@/components/layout/Sidebar";
import type { Proposal } from "@/api/types";

function renderAt(path: string) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const fakeProposal = (trace_id: string): Proposal => ({
  trace_id,
  created_at: "2026-04-16T10:00:00Z",
  action_type: "yaml_edit",
  risk_class: "STATEFUL",
  reversible: true,
  proposed_by: "analyst",
  description: "d",
  payload: {},
  status: "pending",
  decided_by: null,
  decided_at: null,
  feedback: null,
  expires_at: null,
  required_role: null,
  approved_by: null,
  approver_role: null,
  approver_email: null,
});

describe("Sidebar", () => {
  it("renders the four Phase 1 nav entries", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /approvals/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /agents/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /audit/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /status/i })).toBeInTheDocument();
  });

  it("marks the active route with aria-current=page", async () => {
    renderAt("/audit");
    const link = await screen.findByRole("link", { name: /audit/i });
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("renders the solution switcher", async () => {
    renderAt("/approvals");
    expect(await screen.findByTestId("sidebar-solution")).toHaveTextContent(/solution/i);
  });

  it("the solution switcher links to /home", async () => {
    renderAt("/approvals");
    expect(await screen.findByTestId("sidebar-solution")).toHaveAttribute("href", "/home");
  });

  it("includes the Constitution entry (Phase 5b)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /constitution/i }),
    ).toHaveAttribute("href", "/constitution");
  });

  it("includes the Knowledge entry (Phase 5c)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /knowledge/i }),
    ).toHaveAttribute("href", "/knowledge");
  });

  it("includes the Collective entry (Phase 5a)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /collective/i }),
    ).toHaveAttribute("href", "/collective");
  });

  it("includes the Analyze entry — the SURFACE -> PROPOSE trigger", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /analyze/i }),
    ).toHaveAttribute("href", "/analyze");
  });

  it("includes the Compliance entry (Phase 5f)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /compliance/i }),
    ).toHaveAttribute("href", "/compliance");
  });

  it("includes the Costs entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /costs/i })).toHaveAttribute(
      "href",
      "/costs",
    );
  });

  it("includes the Workflows entry", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /workflows/i }),
    ).toHaveAttribute("href", "/workflows");
  });

  it("includes the Skills & Tools entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /skills/i })).toHaveAttribute(
      "href",
      "/skills",
    );
  });

  it("includes the Organization entry", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /organization/i }),
    ).toHaveAttribute("href", "/organization");
  });

  it("includes the Monitor entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /monitor/i })).toHaveAttribute(
      "href",
      "/monitor",
    );
  });

  it("includes the Goals entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /goals/i })).toHaveAttribute(
      "href",
      "/goals",
    );
  });

  it("includes the Eval entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /eval/i })).toHaveAttribute(
      "href",
      "/eval",
    );
  });

  it("includes the HIL entry", async () => {
    renderAt("/approvals");
    expect(await screen.findByRole("link", { name: /hil/i })).toHaveAttribute(
      "href",
      "/hil",
    );
  });

  it("includes the Activity entry (triage feed)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /activity/i }),
    ).toHaveAttribute("href", "/activity");
  });

  it("includes the Regulatory entry (multi-standard traceability)", async () => {
    renderAt("/approvals");
    expect(
      await screen.findByRole("link", { name: /regulatory/i }),
    ).toHaveAttribute("href", "/regulatory");
  });

  it("shows a pending-approvals badge with the count", async () => {
    vi.mocked(client.listPendingApprovals).mockResolvedValueOnce([
      fakeProposal("a"),
      fakeProposal("b"),
      fakeProposal("c"),
    ]);
    renderAt("/status");
    const badge = await screen.findByTestId("pending-badge");
    expect(badge).toHaveTextContent("3");
  });

  it("hides the badge when nothing is pending", async () => {
    renderAt("/approvals");
    await screen.findByRole("link", { name: /approvals/i });
    expect(screen.queryByTestId("pending-badge")).not.toBeInTheDocument();
  });

  it("hides solution-scoped nav links when no solution is loaded", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValueOnce(null);
    renderAt("/home");
    await screen.findByText(/pick a solution/i);
    expect(screen.queryByRole("link", { name: /^approvals$/i })).not.toBeInTheDocument();
  });

  it("always shows + New solution regardless of solution state", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValueOnce(null);
    renderAt("/home");
    await screen.findByText(/pick a solution/i);
    expect(
      screen.getByRole("link", { name: /new solution/i }),
    ).toHaveAttribute("href", "/onboarding");
  });
});
