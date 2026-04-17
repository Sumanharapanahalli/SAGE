import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  evolutionLeaderboard: vi.fn(),
  evolutionHistory: vi.fn(),
  evolutionAnalytics: vi.fn(),
  evolutionTrain: vi.fn(),
}));

import * as client from "@/api/client";
import { Evolution } from "@/pages/Evolution";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("Evolution page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the leaderboard and history sections", async () => {
    vi.mocked(client.evolutionLeaderboard).mockResolvedValue({
      leaderboard: [
        {
          agent_role: "developer",
          rating: 1205,
          rating_deviation: 90,
          wins: 3,
          losses: 1,
          win_rate: 0.75,
          sessions: 4,
        },
      ],
      stats: { total_agents: 1, total_sessions: 4, avg_rating: 1205 },
    });
    vi.mocked(client.evolutionHistory).mockResolvedValue({
      sessions: [
        {
          session_id: "s1",
          agent_role: "developer",
          exercise_id: "ex_001",
          score: 80,
          passed: true,
          timestamp: "2026-04-16T12:00:00Z",
        },
      ],
    });

    render(<Evolution />, { wrapper: wrapperWith(createTestQueryClient()) });

    await waitFor(() =>
      expect(screen.getAllByText("developer").length).toBeGreaterThan(0),
    );
    expect(screen.getByText(/train an agent/i)).toBeInTheDocument();
    expect(screen.getByText(/recent sessions/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /analytics/i })).toBeInTheDocument();
  });
});
