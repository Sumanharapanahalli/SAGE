import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getCurrentSolution: vi.fn().mockResolvedValue(null),
  listPendingApprovals: vi.fn().mockResolvedValue([]),
}));

import * as client from "@/api/client";
import { Sidebar } from "@/components/layout/Sidebar";
import { findByTestId } from "@testing-library/react";
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
  it("renders the four Phase 1 nav entries", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /approvals/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /agents/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /audit/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /status/i })).toBeInTheDocument();
  });

  it("marks the active route with aria-current=page", () => {
    renderAt("/audit");
    const link = screen.getByRole("link", { name: /audit/i });
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("renders a solution footer", () => {
    renderAt("/approvals");
    expect(screen.getByTestId("sidebar-solution")).toHaveTextContent(/solution/i);
  });

  it("includes the Constitution entry (Phase 5b)", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /constitution/i }),
    ).toHaveAttribute("href", "/constitution");
  });

  it("includes the Knowledge entry (Phase 5c)", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /knowledge/i }),
    ).toHaveAttribute("href", "/knowledge");
  });

  it("includes the Collective entry (Phase 5a)", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /collective/i }),
    ).toHaveAttribute("href", "/collective");
  });

  it("includes the Analyze entry — the SURFACE -> PROPOSE trigger", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /analyze/i }),
    ).toHaveAttribute("href", "/analyze");
  });

  it("includes the Compliance entry (Phase 5f)", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /compliance/i }),
    ).toHaveAttribute("href", "/compliance");
  });

  it("includes the Costs entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /costs/i })).toHaveAttribute(
      "href",
      "/costs",
    );
  });

  it("includes the Workflows entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /workflows/i })).toHaveAttribute(
      "href",
      "/workflows",
    );
  });

  it("includes the Skills & Tools entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /skills/i })).toHaveAttribute(
      "href",
      "/skills",
    );
  });

  it("includes the Organization entry", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /organization/i }),
    ).toHaveAttribute("href", "/organization");
  });

  it("includes the Monitor entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /monitor/i })).toHaveAttribute(
      "href",
      "/monitor",
    );
  });

  it("includes the Goals entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /goals/i })).toHaveAttribute(
      "href",
      "/goals",
    );
  });

  it("includes the Eval entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /eval/i })).toHaveAttribute(
      "href",
      "/eval",
    );
  });

  it("includes the HIL entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /hil/i })).toHaveAttribute(
      "href",
      "/hil",
    );
  });

  it("shows a pending-approvals badge with the count", async () => {
    vi.mocked(client.listPendingApprovals).mockResolvedValueOnce([
      fakeProposal("a"),
      fakeProposal("b"),
      fakeProposal("c"),
    ]);
    const { container } = renderAt("/status");
    const badge = await findByTestId(container as HTMLElement, "pending-badge");
    expect(badge).toHaveTextContent("3");
  });

  it("hides the badge when nothing is pending", () => {
    renderAt("/approvals");
    expect(screen.queryByTestId("pending-badge")).not.toBeInTheDocument();
  });
});
