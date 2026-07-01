import { useQuery } from "@tanstack/react-query";

import { getMonitorStatus, getSchedulerStatus } from "@/api/client";
import type { DesktopError, MonitorStatus, SchedulerStatus } from "@/api/types";

/** MonitorAgent's polling/thread status. Degrades gracefully sidecar-side —
 * this query never rejects for a "not active" monitor, it resolves to
 * {running: false, ...}. */
export function useMonitorStatus() {
  return useQuery<MonitorStatus, DesktopError>({
    queryKey: ["monitorStatus"],
    queryFn: () => getMonitorStatus(),
  });
}

/** TaskScheduler's running state + schedule count. Same graceful
 * degradation as useMonitorStatus — a "not running" scheduler resolves
 * normally, it does not reject. */
export function useSchedulerStatus() {
  return useQuery<SchedulerStatus, DesktopError>({
    queryKey: ["schedulerStatus"],
    queryFn: () => getSchedulerStatus(),
  });
}
