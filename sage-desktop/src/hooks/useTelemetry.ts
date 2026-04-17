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
