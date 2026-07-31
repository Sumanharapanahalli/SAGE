import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchOrgTemplates,
  onboardingGenerate,
  saveSolution,
  scanFolder,
} from "@/api/client";
import type {
  DesktopError,
  OnboardingParams,
  OnboardingResult,
  OrgTemplatesResult,
  SaveSolutionResult,
  ScanFolderResult,
  SolutionDraftFiles,
} from "@/api/types";
import { solutionsKey } from "@/hooks/useSolutions";

/**
 * Generate a brand-new solution via the onboarding wizard.
 *
 * On a successful `created` response we invalidate the solutions list so
 * the Sidebar picker picks up the new entry. An `exists` status is a
 * soft-fail — we do not invalidate because nothing on disk changed.
 */
export function useOnboardingGenerate() {
  const qc = useQueryClient();
  return useMutation<OnboardingResult, DesktopError, OnboardingParams>({
    mutationFn: (p) => onboardingGenerate(p),
    onSuccess: (data) => {
      if (data.status === "created") {
        qc.invalidateQueries({ queryKey: solutionsKey });
      }
    },
  });
}

interface ScanFolderVars {
  folder_path: string;
  solution_name: string;
  intent?: string;
}

/**
 * Draft a solution from an existing codebase.
 *
 * Writes nothing, so nothing is invalidated here — the solutions list only
 * changes once `useSaveSolution` runs.
 */
export function useScanFolder() {
  return useMutation<ScanFolderResult, DesktopError, ScanFolderVars>({
    mutationFn: (v) => scanFolder(v.folder_path, v.solution_name, v.intent),
  });
}

interface SaveSolutionVars {
  solution_name: string;
  files: SolutionDraftFiles;
}

/** The write step: persists reviewed drafts, so the picker must re-fetch. */
export function useSaveSolution() {
  const qc = useQueryClient();
  return useMutation<SaveSolutionResult, DesktopError, SaveSolutionVars>({
    mutationFn: (v) => saveSolution(v.solution_name, v.files),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: solutionsKey });
    },
  });
}

export const orgTemplatesKey = ["orgTemplates"] as const;

/**
 * Pre-built team structures for the wizard.
 *
 * `staleTime: Infinity` — these come from a YAML file the sidecar caches for
 * its whole lifetime, so re-fetching can never surface anything new.
 */
export function useOrgTemplates() {
  return useQuery<OrgTemplatesResult, DesktopError>({
    queryKey: orgTemplatesKey,
    queryFn: () => fetchOrgTemplates(),
    staleTime: Infinity,
  });
}
