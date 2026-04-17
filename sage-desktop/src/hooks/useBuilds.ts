import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as client from "@/api/client";
import type {
  ApproveBuildParams,
  BuildRunDetail,
  BuildRunSummary,
  DesktopError,
  StartBuildParams,
} from "@/api/types";

export const buildsKey = ["builds"] as const;
export const buildKey = (runId: string) => ["builds", runId] as const;

/**
 * Builds list — polled at 5s so the table reflects state transitions from
 * the orchestrator without the user having to refresh. Matches the cadence
 * we use on the Queue page.
 */
export const useBuilds = () =>
  useQuery<BuildRunSummary[], DesktopError>({
    queryKey: buildsKey,
    queryFn: client.listBuilds,
    refetchInterval: 5000,
  });

/**
 * Single run detail — polled at 3s while the run is active (decomposing,
 * building, integrating) so critic scores and agent results stream in.
 * Awaiting-* and terminal states have no server-side churn, so polling
 * drops off to save CPU.
 */
export const useBuild = (runId: string | undefined) =>
  useQuery<BuildRunDetail, DesktopError>({
    queryKey: buildKey(runId ?? ""),
    queryFn: () => client.getBuild(runId as string),
    enabled: Boolean(runId),
    refetchInterval: (q) => {
      const state = q.state.data?.state;
      if (
        state === "decomposing" ||
        state === "building" ||
        state === "integrating"
      ) {
        return 3000;
      }
      return false;
    },
  });

export function useStartBuild() {
  const qc = useQueryClient();
  return useMutation<BuildRunDetail, DesktopError, StartBuildParams>({
    mutationFn: (p) => client.startBuild(p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: buildsKey });
    },
  });
}

export function useApproveBuildStage() {
  const qc = useQueryClient();
  return useMutation<BuildRunDetail, DesktopError, ApproveBuildParams>({
    mutationFn: (p) => client.approveBuildStage(p),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: buildsKey });
      qc.invalidateQueries({ queryKey: buildKey(variables.run_id) });
    },
  });
}
