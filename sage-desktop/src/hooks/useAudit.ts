import { useQuery } from "@tanstack/react-query";

import {
  auditStats,
  getAuditByTrace,
  listAuditEvents,
  type ListAuditParams,
} from "@/api/client";
import type {
  AuditListResponse,
  AuditStats,
  AuditTraceResponse,
  DesktopError,
} from "@/api/types";

export const auditListKey = (params: ListAuditParams) =>
  ["audit", "list", params] as const;
export const auditTraceKey = (trace_id: string) =>
  ["audit", "trace", trace_id] as const;
export const auditStatsKey = ["audit", "stats"] as const;

export function useAuditEvents(params: ListAuditParams = {}) {
  return useQuery<AuditListResponse, DesktopError>({
    queryKey: auditListKey(params),
    queryFn: () => listAuditEvents(params),
  });
}

export function useAuditByTrace(trace_id: string) {
  return useQuery<AuditTraceResponse, DesktopError>({
    queryKey: auditTraceKey(trace_id),
    queryFn: () => getAuditByTrace(trace_id),
    enabled: trace_id.length > 0,
  });
}

export function useAuditStats() {
  return useQuery<AuditStats, DesktopError>({
    queryKey: auditStatsKey,
    queryFn: () => auditStats(),
  });
}
