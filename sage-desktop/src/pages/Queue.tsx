import { useState } from "react";

import { QueueTile } from "@/components/domain/QueueTile";
import {
  useCancelQueueTask,
  useQueueStatus,
  useQueueTasks,
  useRetryQueueTask,
} from "@/hooks/useQueue";
import type { QueueTask } from "@/api/types";

/**
 * Task queue view with operator recovery controls.
 *
 * The queue used to be visible only as a counts tile on Status: an operator
 * could watch a task wedge but had no way to do anything about it. Cancel and
 * retry are FRAMEWORK CONTROL (Law 1) — the operator acting on their own
 * tooling — so they execute immediately and never enter the proposal queue.
 * They are still written to the audit log.
 */

const FILTERS = [
  "all",
  "pending",
  "in_progress",
  "failed",
  "blocked",
  "cancelled",
  "completed",
] as const;

type Filter = (typeof FILTERS)[number];

/** Cancel is meaningful only while the task can still be stopped or is running. */
const CANCELLABLE = new Set(["pending", "in_progress", "blocked"]);
/** Retry puts a task that ended without succeeding back in the queue. */
const RETRYABLE = new Set(["failed", "cancelled", "blocked"]);

function StatusPill({ status }: { status: string }) {
  const tone =
    status === "failed" || status === "blocked"
      ? "bg-red-100 text-red-800"
      : status === "completed"
        ? "bg-green-100 text-green-800"
        : status === "cancelled"
          ? "bg-slate-200 text-slate-700"
          : status === "in_progress"
            ? "bg-amber-100 text-amber-800"
            : "bg-sky-100 text-sky-800";
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${tone}`}>
      {status}
    </span>
  );
}

export default function Queue() {
  const [filter, setFilter] = useState<Filter>("all");
  const [notice, setNotice] = useState<string | null>(null);

  const status = useQueueStatus();
  const tasks = useQueueTasks(
    filter === "all" ? { limit: 100 } : { status: filter, limit: 100 },
  );
  const cancel = useCancelQueueTask();
  const retry = useRetryQueueTask();

  const busyId =
    cancel.isPending || retry.isPending
      ? ((cancel.variables ?? retry.variables) as string | undefined)
      : undefined;

  const actionError = cancel.error ?? retry.error;

  const onCancel = (task: QueueTask) => {
    setNotice(null);
    cancel.mutate(task.task_id, {
      onSuccess: (res) => {
        // Be honest: an in_progress task is tombstoned, not killed. The queue
        // has no cooperative cancellation, so the worker thread runs on until
        // its own timeout. Saying "cancelled" flatly would be a lie.
        setNotice(
          res.was_running
            ? `Task ${task.task_id.slice(0, 8)} marked cancelled. It was already running — the worker will not pick up new work for it, but the in-flight execution is not killed and runs to its timeout.`
            : `Task ${task.task_id.slice(0, 8)} cancelled before dispatch.`,
        );
      },
    });
  };

  const onRetry = (task: QueueTask) => {
    setNotice(null);
    retry.mutate(task.task_id, {
      onSuccess: () => {
        setNotice(
          `Task ${task.task_id.slice(0, 8)} re-queued as pending. It runs when a worker next drains the queue.`,
        );
      },
    });
  };

  const rows = tasks.data ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div>
        <h2 className="text-lg font-semibold">Task queue</h2>
        <p className="text-sm text-gray-600">
          Cancel or retry a stuck task. These are operator actions — they take
          effect immediately and are recorded in the audit log.
        </p>
      </div>

      {status.isSuccess && <QueueTile status={status.data} />}

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            className={`rounded border px-3 py-1 text-xs ${
              filter === f
                ? "border-sage-600 bg-sage-600 text-white"
                : "border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {notice && (
        <div
          role="status"
          className="rounded border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900"
        >
          {notice}
        </div>
      )}

      {actionError && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          {actionError.kind === "InvalidParams" ||
          actionError.kind === "SidecarDown"
            ? `${actionError.kind}: ${actionError.detail.message}`
            : `Action failed (${actionError.kind}).`}
        </div>
      )}

      {tasks.isError && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          Could not load tasks: {tasks.error?.kind ?? "unknown error"}
        </div>
      )}

      <div className="overflow-x-auto rounded border border-sage-100 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-sage-100 text-xs uppercase text-gray-500">
            <tr>
              <th className="p-3">Task</th>
              <th className="p-3">Status</th>
              <th className="p-3">Retries</th>
              <th className="p-3">Created</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td className="p-6 text-center text-slate-500" colSpan={5}>
                  {tasks.isLoading ? "Loading…" : "No tasks."}
                </td>
              </tr>
            )}
            {rows.map((task) => {
              const isBusy = busyId === task.task_id;
              return (
                <tr key={task.task_id} className="border-b border-gray-100">
                  <td className="p-3">
                    <div className="font-mono text-xs">{task.task_type}</div>
                    <div className="font-mono text-[10px] text-slate-400">
                      {task.task_id}
                    </div>
                    {task.error && (
                      <div className="mt-1 text-xs text-red-700">
                        {task.error}
                      </div>
                    )}
                  </td>
                  <td className="p-3">
                    <StatusPill status={task.status} />
                  </td>
                  <td className="p-3 text-xs text-slate-600">
                    {task.retry_count ?? 0}/{task.max_retries ?? 0}
                  </td>
                  <td className="p-3 text-xs text-slate-600">
                    {task.created_at
                      ? new Date(task.created_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="p-3">
                    <div className="flex gap-2">
                      <button
                        type="button"
                        aria-label={`Cancel task ${task.task_id}`}
                        disabled={isBusy || !CANCELLABLE.has(task.status)}
                        onClick={() => onCancel(task)}
                        className="rounded border border-red-400 px-3 py-1 text-xs text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        aria-label={`Retry task ${task.task_id}`}
                        disabled={isBusy || !RETRYABLE.has(task.status)}
                        onClick={() => onRetry(task)}
                        className="rounded border border-sage-600 px-3 py-1 text-xs text-sage-700 hover:bg-sage-50 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        Retry
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
