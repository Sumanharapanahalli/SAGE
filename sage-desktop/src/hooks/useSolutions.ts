import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  getCurrentSolution,
  listSolutions,
  removeSolution,
  switchSolution,
  unloadSolution,
} from "@/api/client";
import { clearLastSolution } from "@/lib/lastSolution";
import type {
  CurrentSolution,
  DesktopError,
  RemoveSolutionMode,
  RemoveSolutionResult,
  SolutionRef,
  SwitchSolutionResult,
  UnloadSolutionResult,
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

/**
 * Unload the active solution — the sidecar respawns with no solution and the
 * app falls back to the picker. Nothing on disk is touched.
 *
 * `clearLastSolution()` runs FIRST: Home auto-reopens `getLastSolution()` on
 * mount, so leaving it set would instantly re-switch into the solution the
 * operator just closed.
 */
export function useUnloadSolution() {
  const qc = useQueryClient();
  return useMutation<UnloadSolutionResult, DesktopError, void>({
    mutationFn: () => unloadSolution(),
    onSuccess: () => {
      clearLastSolution();
      qc.invalidateQueries();
    },
  });
}

export interface RemoveVars {
  name: string;
  mode?: RemoveSolutionMode;
  /** Required (and must equal `name`) when mode is "delete". */
  confirm?: string;
}

/**
 * Deregister a solution. Archive by default (reversible); "delete" is a real
 * rmtree and the sidecar refuses it unless `confirm === name`.
 *
 * Only offered for solutions that are NOT active — the running sidecar holds
 * the active solution's `.sage/` SQLite files open.
 */
export function useRemoveSolution() {
  const qc = useQueryClient();
  return useMutation<RemoveSolutionResult, DesktopError, RemoveVars>({
    mutationFn: (v) => removeSolution(v.name, v.mode ?? "archive", v.confirm),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: solutionsKey });
    },
  });
}
