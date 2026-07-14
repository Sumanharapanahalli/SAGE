import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as client from "@/api/client";
import type {
  DesktopError,
  QueueCancelResult,
  QueueRetryResult,
  QueueStatus,
  QueueTask,
} from "@/api/types";

export const queueKey = ["queue"] as const;

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
    // A wedged task is a live problem the operator is watching — keep the row
    // and its status current without a manual refresh, same cadence as status.
    refetchInterval: 5000,
  });

/**
 * Operator cancel. Framework control (Law 1): executes immediately, never goes
 * through the proposal queue — this is the operator acting on their own tooling,
 * not an agent proposing anything.
 */
export function useCancelQueueTask() {
  const qc = useQueryClient();
  return useMutation<QueueCancelResult, DesktopError, string>({
    mutationFn: (taskId) => client.cancelQueueTask(taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queueKey });
    },
  });
}

/** Operator retry — re-queue a failed/cancelled/blocked task. Immediate. */
export function useRetryQueueTask() {
  const qc = useQueryClient();
  return useMutation<QueueRetryResult, DesktopError, string>({
    mutationFn: (taskId) => client.retryQueueTask(taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queueKey });
    },
  });
}
