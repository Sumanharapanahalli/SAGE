import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  constitutionCheckAction,
  constitutionGet,
  constitutionUpdate,
} from "@/api/client";
import type {
  CheckActionResult,
  ConstitutionData,
  ConstitutionState,
  ConstitutionUpdateResult,
  DesktopError,
} from "@/api/types";

export const constitutionKey = ["constitution"] as const;

export function useConstitution() {
  return useQuery<ConstitutionState, DesktopError>({
    queryKey: constitutionKey,
    queryFn: () => constitutionGet(),
    staleTime: 0,
  });
}

interface UpdateArgs {
  data: ConstitutionData;
  changed_by?: string;
}

export function useUpdateConstitution() {
  const qc = useQueryClient();
  return useMutation<ConstitutionUpdateResult, DesktopError, UpdateArgs>({
    mutationFn: ({ data, changed_by }) =>
      constitutionUpdate(data, changed_by),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: constitutionKey });
    },
  });
}

/**
 * Hand-driven mutation: the action checker runs on demand rather than on
 * every keystroke, so this is a mutation rather than a query.
 */
export function useCheckAction() {
  return useMutation<CheckActionResult, DesktopError, string>({
    mutationFn: (desc) => constitutionCheckAction(desc),
  });
}
