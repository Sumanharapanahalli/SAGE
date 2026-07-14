import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueueTile } from "@/components/domain/QueueTile";

describe("QueueTile", () => {
  it("renders queue counts", () => {
    render(
      <QueueTile
        status={{
          pending: 3, in_progress: 1, completed: 5, failed: 0, blocked: 0,
          cancelled: 2, parallel_enabled: true, max_workers: 4,
        }}
      />,
    );
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("shows finished tasks under the status the framework actually emits", () => {
    // TaskStatus emits "completed"/"cancelled", never "done". The tile used to
    // key on "done", so the count silently rendered blank.
    render(
      <QueueTile
        status={{
          pending: 0, in_progress: 0, completed: 7, failed: 0, blocked: 0,
          cancelled: 4, parallel_enabled: false, max_workers: 0,
        }}
      />,
    );
    expect(screen.getByText(/completed/i)).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText(/cancelled/i)).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
  });
});
