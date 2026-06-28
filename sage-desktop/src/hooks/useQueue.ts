import { useQuery } from "@tanstack/react-query";
import * as client from "@/api/client";
import type { DesktopError, QueueStatus, QueueTask } from "@/api/types";

export const useQueueStatus = () =>
  useQuery<QueueStatus, DesktopError>({
    queryKey: ["queue", "status"],
    queryFn: client.getQueueStatus,
    refetchInterval: 5000,
  });

export const useQueueTasks = (params: { status?: string; limit?: number } = {}) =>
  useQuery<QueueTask[], DesktopError>({
    queryKey: ["queue", "tasks", params.status ?? "all", params.limit ?? 50],
    queryFn: () => client.listQueueTasks(params),
  });
