import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Compliance from "@/pages/Compliance";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listComplianceDomains: vi.fn(),
    getComplianceChecklist: vi.fn(),
    assessComplianceGap: vi.fn(),
  };
});

const DOMAINS = {
  domains: [
    {
      domain: "medtech",
      standard: "IEC 62304",
      description: "Medical device software",
      authority: "FDA",
      risk_levels: ["CLASS_A", "CLASS_C"],
      hil_required_for: ["CLASS_C"],
    },
  ],
};

const CHECKLIST = {
  domain: "medtech",
  risk_level: "CLASS_C",
  standard: "IEC 62304",
  description: "",
  authority: "FDA",
  hil_testing_required: true,
  total_items: 1,
  flags: 0,
  required_tasks: 1,
  artifacts: 0,
  items: [
    {
      id: "TASK-RISK_ANALYSIS",
      type: "required_task" as const,
      level: "REQUIRED",
      description: "Task type 'RISK_ANALYSIS' must be completed",
      clause: "IEC 62304",
      hil_required: false,
      status: null,
      evidence_ref: null,
      notes: "",
    },
  ],
};

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Compliance />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Compliance page", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists domains and loads the checklist for the selected one", async () => {
    vi.mocked(client.listComplianceDomains).mockResolvedValue(DOMAINS);
    vi.mocked(client.getComplianceChecklist).mockResolvedValue(CHECKLIST);
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/medtech/i)).toBeInTheDocument(),
    );
    await waitFor(() =>
      expect(client.getComplianceChecklist).toHaveBeenCalledWith(
        "medtech",
        "CLASS_A",
      ),
    );
    await waitFor(() =>
      expect(screen.getByText(/RISK_ANALYSIS/i)).toBeInTheDocument(),
    );
  });

  it("runs a gap assessment against checked tasks", async () => {
    vi.mocked(client.listComplianceDomains).mockResolvedValue(DOMAINS);
    vi.mocked(client.getComplianceChecklist).mockResolvedValue(CHECKLIST);
    vi.mocked(client.assessComplianceGap).mockResolvedValue({
      domain: "medtech",
      risk_level: "CLASS_A",
      required_tasks: ["RISK_ANALYSIS"],
      completed_tasks: ["RISK_ANALYSIS"],
      missing_tasks: [],
      hil_tasks_missing: [],
      compliance_pct: 100,
      compliant: true,
      blocking_gaps: [],
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/RISK_ANALYSIS/i)).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /assess/i }));

    await waitFor(() =>
      expect(client.assessComplianceGap).toHaveBeenCalledWith(
        "medtech",
        "CLASS_A",
        ["RISK_ANALYSIS"],
      ),
    );
    await waitFor(() =>
      expect(screen.getByText(/100/)).toBeInTheDocument(),
    );
  });

  it("shows an error banner when the domains query fails", async () => {
    vi.mocked(client.listComplianceDomains).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "domains boom" },
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/domains boom/i),
    );
  });

  it("shows a loading indicator while domains load", () => {
    vi.mocked(client.listComplianceDomains).mockReturnValue(
      new Promise(() => {}),
    );
    renderPage();

    expect(screen.getByText(/loading domains/i)).toBeInTheDocument();
  });
});
