import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApprovalCard } from "@/components/domain/ApprovalCard";
import type { Proposal } from "@/api/types";

const base: Proposal = {
  trace_id: "t-1",
  created_at: "2026-04-16T10:00:00Z",
  action_type: "yaml_edit",
  risk_class: "STATEFUL",
  reversible: true,
  proposed_by: "analyst",
  description: "edit prompts.yaml",
  payload: { path: "prompts.yaml" },
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

describe("ApprovalCard", () => {
  it("shows description, action type, and risk class", () => {
    render(
      <ApprovalCard
        proposal={base}
        onApprove={() => {}}
        onReject={() => {}}
      />,
    );
    expect(screen.getByText(/edit prompts\.yaml/)).toBeInTheDocument();
    expect(screen.getByText(/yaml_edit/)).toBeInTheDocument();
    expect(screen.getByText(/STATEFUL/)).toBeInTheDocument();
  });

  it("calls onApprove when Approve is clicked", async () => {
    const onApprove = vi.fn();
    render(
      <ApprovalCard
        proposal={base}
        onApprove={onApprove}
        onReject={() => {}}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /approve/i }));
    expect(onApprove).toHaveBeenCalledWith("t-1");
  });

  it("calls onReject when Reject is clicked", async () => {
    const onReject = vi.fn();
    render(
      <ApprovalCard
        proposal={base}
        onApprove={() => {}}
        onReject={onReject}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onReject).toHaveBeenCalledWith("t-1");
  });

  it("disables buttons when isPending", () => {
    render(
      <ApprovalCard
        proposal={base}
        onApprove={() => {}}
        onReject={() => {}}
        isPending
      />,
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /reject/i })).toBeDisabled();
  });
});
