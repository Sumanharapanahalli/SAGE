import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listPendingApprovals: vi.fn(),
  getApproval: vi.fn(),
  approveProposal: vi.fn(),
  rejectProposal: vi.fn(),
  batchApprove: vi.fn(),
}));

import * as client from "@/api/client";
import { Approvals } from "@/pages/Approvals";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";
import type { Proposal } from "@/api/types";

const p1: Proposal = {
  trace_id: "t-1",
  created_at: "2026-04-16T10:00:00Z",
  action_type: "yaml_edit",
  risk_class: "STATEFUL",
  reversible: true,
  proposed_by: "analyst",
  description: "edit prompts.yaml",
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
};

describe("Approvals page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows loading then a list of proposals", async () => {
    vi.mocked(client.listPendingApprovals).mockResolvedValue([p1]);
    render(<Approvals />, { wrapper: wrapperWith(createTestQueryClient()) });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(/edit prompts\.yaml/)).toBeInTheDocument(),
    );
  });

  it("shows an empty state when nothing is pending", async () => {
    vi.mocked(client.listPendingApprovals).mockResolvedValue([]);
    render(<Approvals />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/nothing pending/i)).toBeInTheDocument(),
    );
  });

  it("shows error banner on failure", async () => {
    vi.mocked(client.listPendingApprovals).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "dead" },
    });
    render(<Approvals />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i),
    );
  });

  it("calls approveProposal when Approve is clicked", async () => {
    vi.mocked(client.listPendingApprovals).mockResolvedValue([p1]);
    vi.mocked(client.approveProposal).mockResolvedValue({
      ...p1,
      status: "approved",
    });
    render(<Approvals />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() => screen.getByText(/edit prompts\.yaml/));
    await userEvent.click(screen.getByRole("button", { name: /approve/i }));
    expect(client.approveProposal).toHaveBeenCalledWith(
      "t-1",
      undefined,
      undefined,
    );
  });
});
