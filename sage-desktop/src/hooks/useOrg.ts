import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  addOrgRoute,
  clearSolutionParent,
  createOrgChannel,
  deleteOrgChannel,
  deleteOrgRoute,
  getOrg,
  reloadOrg,
  setSolutionParent,
  updateOrg,
} from "@/api/client";
import type {
  DesktopError,
  OrgChannelResult,
  OrgData,
  OrgParentResult,
  OrgRouteResult,
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


// Every mutation below rewrites org.yaml or a solution's project.yaml, and the
// org graph `useOrg` renders is derived from both — so all of them invalidate
// orgKey rather than trying to patch the cache.

interface ChannelVars {
  name: string;
  producers?: string[];
  consumers?: string[];
}

export function useCreateOrgChannel() {
  const qc = useQueryClient();
  return useMutation<OrgChannelResult, DesktopError, ChannelVars>({
    mutationFn: (v) =>
      createOrgChannel(v.name, v.producers ?? [], v.consumers ?? []),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKey }),
  });
}

export function useDeleteOrgChannel() {
  const qc = useQueryClient();
  return useMutation<OrgChannelResult, DesktopError, string>({
    mutationFn: (name) => deleteOrgChannel(name),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKey }),
  });
}

interface RouteVars {
  solution: string;
  target: string;
}

export function useAddOrgRoute() {
  const qc = useQueryClient();
  return useMutation<OrgRouteResult, DesktopError, RouteVars>({
    mutationFn: (v) => addOrgRoute(v.solution, v.target),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKey }),
  });
}

export function useDeleteOrgRoute() {
  const qc = useQueryClient();
  return useMutation<OrgRouteResult, DesktopError, RouteVars>({
    mutationFn: (v) => deleteOrgRoute(v.solution, v.target),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKey }),
  });
}

interface ParentVars {
  solution: string;
  parent: string;
}

export function useSetSolutionParent() {
  const qc = useQueryClient();
  return useMutation<OrgParentResult, DesktopError, ParentVars>({
    mutationFn: (v) => setSolutionParent(v.solution, v.parent),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKey }),
  });
}

export function useClearSolutionParent() {
  const qc = useQueryClient();
  return useMutation<OrgParentResult, DesktopError, string>({
    mutationFn: (solution) => clearSolutionParent(solution),
    onSuccess: () => qc.invalidateQueries({ queryKey: orgKey }),
  });
}
