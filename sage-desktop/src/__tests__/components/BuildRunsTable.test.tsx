import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BuildRunsTable } from "@/components/domain/BuildRunsTable";
import type { BuildRunSummary } from "@/api/types";

const rows: BuildRunSummary[] = [
  {
    run_id: "r1",
    solution_name: "yoga",
    state: "awaiting_plan",
    created_at: "2026-04-17T12:00:00Z",
    task_count: 0,
  },
  {
    run_id: "r2",
    solution_name: "dance",
    state: "completed",
    created_at: "2026-04-17T11:00:00Z",
    task_count: 8,
  },
];

describe("BuildRunsTable", () => {
  it("renders an empty state when there are no runs", () => {
    render(<BuildRunsTable runs={[]} selectedId={null} onSelect={vi.fn()} />);
    expect(screen.getByText(/no build runs/i)).toBeInTheDocument();
  });

  it("renders one row per run and fires onSelect when clicked", () => {
    const onSelect = vi.fn();
    render(
      <BuildRunsTable runs={rows} selectedId={null} onSelect={onSelect} />,
    );
    expect(screen.getByText("yoga")).toBeInTheDocument();
    expect(screen.getByText("dance")).toBeInTheDocument();
    fireEvent.click(screen.getByText("r1"));
    expect(onSelect).toHaveBeenCalledWith("r1");
  });

  it("highlights the selected row", () => {
    render(<BuildRunsTable runs={rows} selectedId="r2" onSelect={vi.fn()} />);
    const selected = screen.getByText("r2").closest("tr");
    expect(selected?.className).toMatch(/bg-sage/);
  });
});
