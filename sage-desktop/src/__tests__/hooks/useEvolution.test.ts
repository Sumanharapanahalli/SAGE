import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  evolutionLeaderboard: vi.fn(),
  evolutionHistory: vi.fn(),
  evolutionAnalytics: vi.fn(),
  evolutionTrain: vi.fn(),
}));

import * as client from "@/api/client";
import {
  historyKey,
  leaderboardKey,
  useAnalytics,
  useHistory,
  useLeaderboard,
  useTrainAgent,
} from "@/hooks/useEvolution";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("useLeaderboard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns leaderboard data", async () => {
    vi.mocked(client.evolutionLeaderboard).mockResolvedValue({
      leaderboard: [
        {
          agent_role: "developer",
          rating: 1200,
          rating_deviation: 90,
          wins: 10,
          losses: 5,
          win_rate: 0.66,
          sessions: 15,
        },
      ],
      stats: { total_agents: 1, total_sessions: 15, avg_rating: 1200 },
    });
    const { result } = renderHook(() => useLeaderboard(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.leaderboard[0].agent_role).toBe("developer");
  });
});

describe("useHistory", () => {
  beforeEach(() => vi.clearAllMocks());

  it("passes limit through to client", async () => {
    vi.mocked(client.evolutionHistory).mockResolvedValue({ sessions: [] });
    renderHook(() => useHistory(25), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() =>
      expect(client.evolutionHistory).toHaveBeenCalledWith(25),
    );
  });
});

describe("useAnalytics", () => {
  beforeEach(() => vi.clearAllMocks());

  it("only runs when a role is selected", async () => {
    vi.mocked(client.evolutionAnalytics).mockResolvedValue({ score_trend: [] });
    const { rerender } = renderHook(
      ({ role }: { role: string }) => useAnalytics(role),
      {
        wrapper: wrapperWith(createTestQueryClient()),
        initialProps: { role: "" },
      },
    );
    expect(client.evolutionAnalytics).not.toHaveBeenCalled();
    rerender({ role: "developer" });
    await waitFor(() =>
      expect(client.evolutionAnalytics).toHaveBeenCalledWith(
        "developer",
        undefined,
      ),
    );
  });
});

describe("useTrainAgent", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invalidates leaderboard and history on success", async () => {
    vi.mocked(client.evolutionTrain).mockResolvedValue({
      session_id: "s1",
      agent_role: "developer",
      status: "completed",
      elo_before: 1200,
      elo_after: 1220,
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useTrainAgent(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ role: "developer" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const keys = spy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(leaderboardKey);
    expect(keys).toContainEqual(historyKey);
  });
});
