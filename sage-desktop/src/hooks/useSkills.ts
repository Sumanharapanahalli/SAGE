import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listMcpTools,
  listSkills,
  reloadSkills,
  setSkillVisibility,
} from "@/api/client";
import type {
  DesktopError,
  McpToolsResult,
  SkillsListResult,
  SkillsReloadResult,
  SkillVisibilitySetResult,
} from "@/api/types";

export const skillsKey = ["skills"] as const;
export const mcpToolsKey = ["mcpTools"] as const;

export function useSkills(includeDisabled?: boolean) {
  return useQuery<SkillsListResult, DesktopError>({
    queryKey: [...skillsKey, includeDisabled ?? false],
    queryFn: () => listSkills(includeDisabled),
  });
}

interface SetVisibilityVars {
  name: string;
  visibility: string;
}

/** Framework control — visibility toggles are the operator's own action,
 * not an agent proposal, so no HITL approval is involved (matches the web
 * API's `/skills/visibility` docstring). Invalidates the skills query on
 * success so the table reflects the new tier immediately. */
export function useSetSkillVisibility() {
  const qc = useQueryClient();
  return useMutation<SkillVisibilitySetResult, DesktopError, SetVisibilityVars>({
    mutationFn: (v) => setSkillVisibility(v.name, v.visibility),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: skillsKey });
    },
  });
}

/** Framework control — hot-reloads all skills from disk. Invalidates the
 * skills query on success so stale in-memory visibility edits are
 * replaced by what's actually on disk. */
export function useReloadSkills() {
  const qc = useQueryClient();
  return useMutation<SkillsReloadResult, DesktopError, void>({
    mutationFn: () => reloadSkills(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: skillsKey });
    },
  });
}

export function useMcpTools() {
  return useQuery<McpToolsResult, DesktopError>({
    queryKey: mcpToolsKey,
    queryFn: () => listMcpTools(),
  });
}
