import { useState } from "react";
import {
  useGoals,
  useCreateGoal,
  useUpdateGoal,
  useDeleteGoal,
} from "@/hooks/useGoals";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { toDesktopError } from "@/api/client";
import type { GoalStatus } from "@/api/types";

const STATUS_OPTIONS: GoalStatus[] = ["on_track", "at_risk", "off_track", "done"];

export default function Goals() {
  const list = useGoals();
  const create = useCreateGoal();
  const update = useUpdateGoal();
  const del = useDeleteGoal();

  const [title, setTitle] = useState("");
  const [quarter, setQuarter] = useState("");
  const [owner, setOwner] = useState("");
  const [status, setStatus] = useState<GoalStatus>("on_track");
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !quarter.trim()) return;
    create.mutate(
      { title, quarter, owner, status },
      {
        onSuccess: () => {
          setTitle("");
          setQuarter("");
          setOwner("");
          setStatus("on_track");
        },
      },
    );
  };

  const createError = create.error ? toDesktopError(create.error) : null;
  const deleteError = del.error ? toDesktopError(del.error) : null;

  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">Goals</h2>

      <form onSubmit={handleSubmit} className="mb-6 space-y-3 rounded border border-gray-200 p-4">
        <h3 className="font-semibold">New goal</h3>
        <label className="block">
          <span className="block text-sm font-medium">Title</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">Quarter</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            placeholder="2026-Q3"
            value={quarter}
            onChange={(e) => setQuarter(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">Owner</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">Status</span>
          <select
            className="mt-1 rounded border border-gray-300 p-2"
            value={status}
            onChange={(e) => setStatus(e.target.value as GoalStatus)}
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          disabled={create.isPending}
          className="rounded bg-sage-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {create.isPending ? "Creating…" : "Create"}
        </button>
      </form>

      <ErrorBanner error={createError} />

      <div className="space-y-3">
        {list.isLoading && <p>Loading…</p>}
        <ErrorBanner error={list.error} />
        <ErrorBanner error={deleteError} />
        {list.isSuccess && list.data.length === 0 && (
          <p className="text-sm text-gray-500">No goals yet.</p>
        )}
        {list.data?.map((goal) => (
          <div
            key={goal.id}
            className="flex items-center justify-between rounded border border-sage-100 bg-white p-4"
          >
            <div>
              <div className="font-medium">{goal.title}</div>
              <div className="text-sm text-slate-500">
                {goal.quarter} · {goal.status} · {goal.owner || "unassigned"} ·{" "}
                {goal.key_results.length} key result
                {goal.key_results.length === 1 ? "" : "s"}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <select
                aria-label={`status for ${goal.title}`}
                className="rounded border border-gray-300 p-1.5 text-sm"
                value={goal.status}
                disabled={update.isPending}
                onChange={(e) =>
                  update.mutate({
                    goal_id: goal.id,
                    status: e.target.value as GoalStatus,
                  })
                }
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              {confirmingId === goal.id ? (
                <>
                  <button
                    type="button"
                    onClick={() => {
                      del.mutate(goal.id);
                      setConfirmingId(null);
                    }}
                    disabled={del.isPending}
                    className="rounded border border-red-300 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmingId(null)}
                    className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => setConfirmingId(goal.id)}
                  className="rounded border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50"
                >
                  Delete
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
