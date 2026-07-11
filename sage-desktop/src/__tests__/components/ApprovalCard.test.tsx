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

  it("reject is a two-step flow that captures feedback", async () => {
    const onReject = vi.fn();
    render(
      <ApprovalCard
        proposal={base}
        onApprove={() => {}}
        onReject={onReject}
      />,
    );
    // First click reveals the feedback textarea; it does NOT reject immediately.
    await userEvent.click(screen.getByRole("button", { name: /^reject$/i }));
    expect(onReject).not.toHaveBeenCalled();

    const box = screen.getByPlaceholderText(/why.*reject/i);
    await userEvent.type(box, "prompt is too vague");
    await userEvent.click(
      screen.getByRole("button", { name: /confirm rejection/i }),
    );
    expect(onReject).toHaveBeenCalledWith("t-1", "prompt is too vague");
  });

  it("blocks rejection until feedback is given — it is the training signal", async () => {
    // Previously this asserted the opposite (rejection with an empty comment).
    // That was only harmless because the feedback went nowhere: desktop's reject
    // was a bare SQL UPDATE. Now it feeds vector memory (Law 3 / Phase 5), a
    // rejection with no reasoning teaches the system nothing, and web hard-gates
    // this button for the same reason.
    const onReject = vi.fn();
    render(
      <ApprovalCard proposal={base} onApprove={() => {}} onReject={onReject} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /^reject$/i }));

    const confirm = screen.getByRole("button", { name: /confirm rejection/i });
    expect(confirm).toBeDisabled();
    await userEvent.click(confirm);
    expect(onReject).not.toHaveBeenCalled();
  });

  it("shows the proposal payload so the decision is not made blind", async () => {
    render(
      <ApprovalCard proposal={base} onApprove={() => {}} onReject={() => {}} />,
    );
    // The payload (path: prompts.yaml) must be reachable in the DOM — assert
    // the unique JSON line so we don't collide with the description text.
    await userEvent.click(screen.getByText(/details|payload/i));
    expect(screen.getByText(/"path": "prompts\.yaml"/)).toBeInTheDocument();
  });

  it("surfaces whether the action is reversible", () => {
    render(
      <ApprovalCard proposal={base} onApprove={() => {}} onReject={() => {}} />,
    );
    expect(screen.getByText(/reversible/i)).toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: /^reject$/i })).toBeDisabled();
  });
});
