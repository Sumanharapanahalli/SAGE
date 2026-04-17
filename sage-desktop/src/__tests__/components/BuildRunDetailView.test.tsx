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

describe("BuildRunDetailView", () => {
  it("shows approve / reject buttons when state is awaiting_plan", () => {
    render(
      <BuildRunDetailView
        detail={baseDetail}
        isApproving={false}
        approveError={null}
        onApprove={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /approve plan/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /reject/i }),
    ).toBeInTheDocument();
  });

  it("shows approve build button when state is awaiting_build", () => {
    render(
      <BuildRunDetailView
        detail={{ ...baseDetail, state: "awaiting_build" }}
        isApproving={false}
        approveError={null}
        onApprove={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: /approve build/i }),
    ).toBeInTheDocument();
  });

  it("hides approval buttons for terminal states", () => {
    render(
      <BuildRunDetailView
        detail={{ ...baseDetail, state: "completed" }}
        isApproving={false}
        approveError={null}
        onApprove={vi.fn()}
      />,
    );
    expect(screen.queryByRole("button", { name: /approve/i })).toBeNull();
  });

  it("fires onApprove with approved=true when approve is clicked", () => {
    const onApprove = vi.fn();
    render(
      <BuildRunDetailView
        detail={baseDetail}
        isApproving={false}
        approveError={null}
        onApprove={onApprove}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /approve plan/i }));
    expect(onApprove).toHaveBeenCalledWith({
      run_id: "r1",
      approved: true,
      feedback: "",
    });
  });

  it("fires onApprove with approved=false and trimmed feedback when rejecting", () => {
    const onApprove = vi.fn();
    render(
      <BuildRunDetailView
        detail={baseDetail}
        isApproving={false}
        approveError={null}
        onApprove={onApprove}
      />,
    );
    fireEvent.change(screen.getByLabelText(/feedback/i), {
      target: { value: "  not enough context  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    expect(onApprove).toHaveBeenCalledWith({
      run_id: "r1",
      approved: false,
      feedback: "not enough context",
    });
  });

  it("renders typed error banners", () => {
    render(
      <BuildRunDetailView
        detail={baseDetail}
        isApproving={false}
        approveError={{
          kind: "InvalidParams",
          detail: { message: "Run is not awaiting approval (state: building)" },
        }}
        onApprove={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/InvalidParams/);
  });
});
