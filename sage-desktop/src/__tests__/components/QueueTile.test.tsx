import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueueTile } from "@/components/domain/QueueTile";

describe("QueueTile", () => {
  it("renders queue counts", () => {
    render(
      <QueueTile
        status={{
          pending: 3, in_progress: 1, done: 5, failed: 0, blocked: 0,
          parallel_enabled: true, max_workers: 4,
        }}
      />,
    );
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });
});
