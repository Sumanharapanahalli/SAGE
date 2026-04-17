import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as client from "@/api/client";
import type { DesktopError, UpdateStatus } from "@/api/types";

export const updateKey = ["update"] as const;

/**
 * Query the update endpoint on demand. Disabled by default so the user
 * triggers the check explicitly — we don't want every Settings mount to
 * hit GitHub.
 */
export function useUpdateCheck(enabled = false) {
  return useQuery<UpdateStatus, DesktopError>({
    queryKey: updateKey,
    queryFn: () => client.checkUpdate(),
    enabled,
    staleTime: 60_000,
  });
}

export function useInstallUpdate() {
  const qc = useQueryClient();
  return useMutation<void, DesktopError, void>({
    mutationFn: () => client.installUpdate(),
    onSuccess: () => qc.invalidateQueries({ queryKey: updateKey }),
  });
}
