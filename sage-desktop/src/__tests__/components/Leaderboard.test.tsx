import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Leaderboard } from "@/components/domain/Leaderboard";
import type { LeaderboardEntry } from "@/api/types";

const rows: LeaderboardEntry[] = [
  {
    agent_role: "developer",
    rating: 1205.4,
    rating_deviation: 92.1,
    wins: 8,
    losses: 4,
    win_rate: 0.667,
    sessions: 12,
  },
  {
    agent_role: "analyst",
    rating: 1180.0,
    rating_deviation: 110.0,
    wins: 3,
    losses: 5,
    win_rate: 0.375,
    sessions: 8,
  },
];

describe("Leaderboard", () => {
  it("renders one row per entry", () => {
    render(
      <Leaderboard rows={rows} selectedRole={null} onSelect={() => {}} />,
    );
    expect(screen.getByText("developer")).toBeInTheDocument();
    expect(screen.getByText("analyst")).toBeInTheDocument();
    expect(screen.getByText("1205.4")).toBeInTheDocument();
    expect(screen.getByText("67%")).toBeInTheDocument();
  });

  it("calls onSelect with the clicked role", () => {
    const onSelect = vi.fn();
    render(
      <Leaderboard rows={rows} selectedRole={null} onSelect={onSelect} />,
    );
    fireEvent.click(screen.getByText("developer"));
    expect(onSelect).toHaveBeenCalledWith("developer");
  });

  it("renders empty state when rows is empty", () => {
    render(
      <Leaderboard rows={[]} selectedRole={null} onSelect={() => {}} />,
    );
    expect(screen.getByText(/no agents yet/i)).toBeInTheDocument();
  });
});
