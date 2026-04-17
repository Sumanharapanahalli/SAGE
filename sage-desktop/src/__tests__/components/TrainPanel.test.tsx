import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TrainPanel } from "@/components/domain/TrainPanel";

describe("TrainPanel", () => {
  it("disables submit until a role is entered", () => {
    const onTrain = vi.fn();
    render(
      <TrainPanel
        isPending={false}
        error={null}
        result={null}
        onTrain={onTrain}
      />,
    );
    const button = screen.getByRole("button", { name: /run training round/i });
    expect(button).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText(/developer/i), {
      target: { value: "developer" },
    });
    expect(button).not.toBeDisabled();
  });

  it("submits the trimmed role and optional fields", () => {
    const onTrain = vi.fn();
    render(
      <TrainPanel
        isPending={false}
        error={null}
        result={null}
        onTrain={onTrain}
      />,
    );
    fireEvent.change(screen.getByPlaceholderText(/developer/i), {
      target: { value: "  developer  " },
    });
    fireEvent.change(screen.getByPlaceholderText(/easy \| medium \| hard/i), {
      target: { value: "medium" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /run training round/i }),
    );
    expect(onTrain).toHaveBeenCalledWith({
      role: "developer",
      difficulty: "medium",
    });
  });

  it("shows the training result when one is provided", () => {
    render(
      <TrainPanel
        isPending={false}
        error={null}
        result={{
          session_id: "abc123",
          agent_role: "developer",
          status: "completed",
          grade: { score: 82.5, passed: true },
          elo_before: 1200,
          elo_after: 1215.5,
        }}
        onTrain={() => {}}
      />,
    );
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
    expect(screen.getByText(/completed/)).toBeInTheDocument();
    expect(screen.getByText(/82.5/)).toBeInTheDocument();
    expect(screen.getByText(/1200.0/)).toBeInTheDocument();
    expect(screen.getByText(/1215.5/)).toBeInTheDocument();
  });
});
