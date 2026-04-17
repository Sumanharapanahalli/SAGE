import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RecentHistory } from "@/components/domain/RecentHistory";

describe("RecentHistory", () => {
  it("renders each session with role, score, and status", () => {
    render(
      <RecentHistory
        sessions={[
          {
            session_id: "s1",
            agent_role: "developer",
            exercise_id: "ex_001",
            score: 81.2,
            passed: true,
            timestamp: "2026-04-16T12:00:00Z",
          },
          {
            session_id: "s2",
            agent_role: "analyst",
            exercise_id: "ex_002",
            score: 42.0,
            passed: false,
            timestamp: "2026-04-16T13:00:00Z",
          },
        ]}
      />,
    );
    expect(screen.getByText("developer")).toBeInTheDocument();
    expect(screen.getByText("81.2")).toBeInTheDocument();
    expect(screen.getByText(/passed/i)).toBeInTheDocument();
    expect(screen.getByText("analyst")).toBeInTheDocument();
    expect(screen.getByText("42.0")).toBeInTheDocument();
    expect(screen.getByText(/failed/i)).toBeInTheDocument();
  });

  it("renders empty state when there are no sessions", () => {
    render(<RecentHistory sessions={[]} />);
    expect(screen.getByText(/no training history/i)).toBeInTheDocument();
  });
});
