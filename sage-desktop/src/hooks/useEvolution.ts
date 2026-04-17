import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  evolutionAnalytics,
  evolutionHistory,
  evolutionLeaderboard,
  evolutionTrain,
} from "@/api/client";
import type {
  AnalyticsResult,
  DesktopError,
  HistoryResult,
  LeaderboardResult,
  TrainParams,
  TrainResult,
} from "@/api/types";

export const leaderboardKey = ["evolution", "leaderboard"] as const;
export const historyKey = ["evolution", "history"] as const;
export const analyticsKey = (role: string, skill = "") =>
  ["evolution", "analytics", role, skill] as const;

export function useLeaderboard() {
  return useQuery<LeaderboardResult, DesktopError>({
    queryKey: leaderboardKey,
    queryFn: () => evolutionLeaderboard(),
  });
}

export function useHistory(limit = 50) {
  return useQuery<HistoryResult, DesktopError>({
    queryKey: [...historyKey, limit],
    queryFn: () => evolutionHistory(limit),
  });
}

export function useAnalytics(role: string, skill?: string) {
  return useQuery<AnalyticsResult, DesktopError>({
    queryKey: analyticsKey(role, skill ?? ""),
    queryFn: () => evolutionAnalytics(role, skill),
    enabled: Boolean(role),
  });
}

/**
 * Trigger a gym training round. Invalidates leaderboard + history so the
 * UI reflects the new rating and the new session.
 */
export function useTrainAgent() {
  const qc = useQueryClient();
  return useMutation<TrainResult, DesktopError, TrainParams>({
    mutationFn: (p) => evolutionTrain(p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: leaderboardKey });
      qc.invalidateQueries({ queryKey: historyKey });
    },
  });
}
