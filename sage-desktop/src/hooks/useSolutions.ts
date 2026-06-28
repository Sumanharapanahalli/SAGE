import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  getCurrentSolution,
  listSolutions,
  switchSolution,
} from "@/api/client";
import type {
  CurrentSolution,
  DesktopError,
  SolutionRef,
  SwitchSolutionResult,
} from "@/api/types";

export const solutionsKey = ["solutions"] as const;
export const currentSolutionKey = ["solutions", "current"] as const;

/** List solutions from the SAGE repo root. */
export function useSolutions() {
  return useQuery<SolutionRef[], DesktopError>({
    queryKey: solutionsKey,
    queryFn: () => listSolutions(),
    staleTime: 30_000,
  });
}

/** The solution the sidecar was spawned with (null if unwired). */
export function useCurrentSolution() {
  return useQuery<CurrentSolution | null, DesktopError>({
    queryKey: currentSolutionKey,
    queryFn: () => getCurrentSolution(),
    staleTime: Infinity,
  });
}

export interface SwitchVars {
  name: string;
  path: string;
}

/**
 * Swap the active solution.
 *
 * The backend respawns the sidecar and re-handshakes under the write lock
 * before returning, so on success we invalidate every query — the fresh
 * sidecar has a fresh `.sage/` directory and all cached data is stale.
 */
export function useSwitchSolution() {
  const qc = useQueryClient();
  return useMutation<SwitchSolutionResult, DesktopError, SwitchVars>({
    mutationFn: (v) => switchSolution(v.name, v.path),
    onSuccess: () => {
      qc.invalidateQueries();
    },
  });
}
