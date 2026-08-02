import { useQuery } from "@tanstack/react-query";

import { orchestratorRecent, orchestratorStats } from "@/api/client";
import type {
  DesktopError,
  OrchestratorRecent,
  OrchestratorStats,
} from "@/api/types";

export const orchestratorStatsKey = ["orchestratorStats"] as const;
export const orchestratorRecentKey = (m: string) =>
  ["orchestratorRecent", m] as const;

/** Polls: these counters move while the orchestrator is working, and a stale
 *  dashboard is worse than no dashboard. */
export function useOrchestratorStats() {
  return useQuery<OrchestratorStats, DesktopError>({
    queryKey: orchestratorStatsKey,
    queryFn: () => orchestratorStats(),
    refetchInterval: 5000,
  });
}

/** Held back until a module is actually selected — firing with an empty
 *  module would ask the sidecar for a record set that cannot exist, and it
 *  rejects the call. */
export function useOrchestratorRecent(module: string) {
  return useQuery<OrchestratorRecent, DesktopError>({
    queryKey: orchestratorRecentKey(module),
    queryFn: () => orchestratorRecent(module),
    enabled: module.length > 0,
    refetchInterval: 5000,
  });
}
