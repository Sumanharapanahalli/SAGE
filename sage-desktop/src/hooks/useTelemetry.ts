import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as client from "@/api/client";
import type { DesktopError, TelemetryStatus } from "@/api/types";

export const telemetryKey = ["telemetry"] as const;

export function useTelemetryStatus() {
  return useQuery<TelemetryStatus, DesktopError>({
    queryKey: telemetryKey,
    queryFn: () => client.telemetryGetStatus(),
  });
}

export function useSetTelemetryEnabled() {
  const qc = useQueryClient();
  return useMutation<TelemetryStatus, DesktopError, boolean>({
    mutationFn: (enabled) => client.telemetrySetEnabled(enabled),
    onSuccess: (data) => qc.setQueryData(telemetryKey, data),
  });
}

/**
 * Phase 4.6: trigger the sidecar to flush its buffered events via
 * `telemetry.flush`. Consent is re-checked inside the sidecar, so
 * calling this while opted-out returns `{ sent: 0, reason: "opted_out" }`
 * rather than leaking anything.
 */
export function useFlushTelemetry() {
  return useMutation<{ sent: number; reason: string }, DesktopError, void>({
    mutationFn: () => client.telemetryFlush(),
  });
}
