import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BuildRunDetailView } from "@/components/domain/BuildRunDetailView";
import type { BuildRunDetail } from "@/api/types";

const baseDetail: BuildRunDetail = {
  run_id: "r1",
  solution_name: "yoga",
  state: "awaiting_plan",
  state_description: "waiting for plan approval",
  created_at: "2026-04-17T12:00:00Z",
  updated_at: "2026-04-17T12:00:05Z",
  product_description: "yoga app with 10-min sessions",
  hitl_level: "standard",
  hitl_gates: ["plan"],
  detected_domains: ["mobile"],
  plan: [
    { task_type: "analyze", description: "understand requirements" },
    { task_type: "implement", description: "build it" },
  ],
  task_count: 2,
  critic_scores: [],
  critic_reports: [],
  agent_results: [],
  integration_result: null,
  phase_durations: {},
};

/** Default props — reject is now its own mutation, not an `approved: false`
 * flag on approve, so the view takes its own pending/error/handler triple. */
function renderView(overrides: Partial<React.ComponentProps<typeof BuildRunDetailView>> = {}) {
  const props = {
    detail: baseDetail,
    isApproving: false,
    approveError: null,
    onApprove: vi.fn(),
    isRejecting: false,
    rejectError: null,
    onReject: vi.fn(),
    ...overrides,
  };
  render(<BuildRunDetailView {...props} />);
  return props;
}

describe("BuildRunDetailView", () => {
  it("shows approve / reject buttons when state is awaiting_plan", () => {
    renderView();
    expect(
      screen.getByRole("button", { name: /approve plan/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /reject plan/i }),
    ).toBeInTheDocument();
  });

  it("shows approve/reject build buttons when state is awaiting_build", () => {
    renderView({ detail: { ...baseDetail, state: "awaiting_build" } });
    expect(
      screen.getByRole("button", { name: /approve build/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /reject build/i }),
    ).toBeInTheDocument();
  });

  it("hides approval buttons for terminal states", () => {
    renderView({ detail: { ...baseDetail, state: "completed" } });
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /reject/i })).toBeNull();
  });

  it("fires onApprove with approved=true when approve is clicked", () => {
    const { onApprove } = renderView();
    fireEvent.click(screen.getByRole("button", { name: /approve plan/i }));
    expect(onApprove).toHaveBeenCalledWith({
      run_id: "r1",
      approved: true,
      feedback: "",
    });
  });

  it("fires onReject (NOT onApprove) with trimmed feedback when rejecting", () => {
    // The reject button must hit the dedicated builds.reject RPC — that is the
    // only path that compounds the operator's reasoning into vector memory.
    const { onReject, onApprove } = renderView();
    fireEvent.change(screen.getByLabelText(/rejection reason/i), {
      target: { value: "  not enough context  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /reject plan/i }));
    expect(onReject).toHaveBeenCalledWith({
      run_id: "r1",
      feedback: "not enough context",
    });
    expect(onApprove).not.toHaveBeenCalled();
  });

  it("allows a rejection without feedback (a decision is valid without a reason)", () => {
    const { onReject } = renderView();
    fireEvent.click(screen.getByRole("button", { name: /reject plan/i }));
    expect(onReject).toHaveBeenCalledWith({ run_id: "r1", feedback: "" });
  });

  it("disables both gate buttons while a rejection is in flight", () => {
    renderView({ isRejecting: true });
    expect(screen.getByRole("button", { name: /approve plan/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /rejecting/i })).toBeDisabled();
  });

  it("renders typed error banners", () => {
    renderView({
      approveError: {
        kind: "InvalidParams",
        detail: { message: "Run is not awaiting approval (state: building)" },
      },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(/InvalidParams/);
  });

  it("renders a rejection-specific error banner", () => {
    renderView({
      rejectError: {
        kind: "InvalidParams",
        detail: { message: "Run is not awaiting approval (state: building)" },
      },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(/InvalidParams/);
  });
});
