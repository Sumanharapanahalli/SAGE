import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getOrg, reloadOrg, updateOrg } from "@/api/client";
import type {
  DesktopError,
  OrgData,
  OrgReloadResult,
  OrgUpdateResult,
} from "@/api/types";

export const orgKey = ["org"] as const;

export function useOrg() {
  return useQuery<OrgData, DesktopError>({
    queryKey: orgKey,
    queryFn: () => getOrg(),
  });
}

interface UpdateOrgArgs {
  name?: string;
  mission?: string;
  vision?: string;
  core_values?: string[];
}

export function useUpdateOrg() {
  const qc = useQueryClient();
  return useMutation<OrgUpdateResult, DesktopError, UpdateOrgArgs>({
    mutationFn: (fields) => updateOrg(fields),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: orgKey });
    },
  });
}

export function useReloadOrg() {
  const qc = useQueryClient();
  return useMutation<OrgReloadResult, DesktopError, void>({
    mutationFn: () => reloadOrg(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: orgKey });
    },
  });
}
