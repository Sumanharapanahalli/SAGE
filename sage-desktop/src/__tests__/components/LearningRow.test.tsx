import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { CollectiveLearning } from "@/api/types";
import { LearningRow } from "@/components/domain/LearningRow";

const SHORT: CollectiveLearning = {
  id: "l1",
  author_agent: "analyst",
  author_solution: "medtech",
  topic: "uart",
  title: "UART recovery",
  content: "short content",
  tags: ["uart", "embedded"],
  confidence: 0.75,
  validation_count: 3,
  created_at: "2026-04-17T00:00:00+00:00",
  updated_at: "2026-04-17T00:00:00+00:00",
  source_task_id: "",
};

const LONG: CollectiveLearning = {
  ...SHORT,
  id: "l2",
  content: "x".repeat(500),
};

describe("LearningRow", () => {
  it("renders title, solution/topic, confidence, validation_count, and tags", () => {
    render(<LearningRow learning={SHORT} onValidate={() => {}} />);
    expect(screen.getByText("UART recovery")).toBeInTheDocument();
    expect(screen.getByText(/medtech/)).toBeInTheDocument();
    expect(screen.getAllByText(/uart/).length).toBeGreaterThan(0);
    expect(screen.getByText(/0\.75/)).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument();
    expect(screen.getByText("embedded")).toBeInTheDocument();
  });

  it("shows expand/collapse for long content", () => {
    render(<LearningRow learning={LONG} onValidate={() => {}} />);
    const expandBtn = screen.getByRole("button", { name: /expand/i });
    fireEvent.click(expandBtn);
    expect(
      screen.getByRole("button", { name: /collapse/i }),
    ).toBeInTheDocument();
  });

  it("invokes onValidate when the validate button is clicked", () => {
    const spy = vi.fn();
    render(<LearningRow learning={SHORT} onValidate={spy} />);
    fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    expect(spy).toHaveBeenCalledWith("l1");
  });
});
