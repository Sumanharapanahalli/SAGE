import { useState } from "react";

import { toDesktopError } from "@/api/client";
import type { WorkflowRunStatus } from "@/api/types";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useResumeWorkflow,
  useRunWorkflow,
  useWorkflowList,
  useWorkflowStatus,
} from "@/hooks/useWorkflows";

/** Parse a textarea's contents as a JSON object. Blank input is treated as
 * "{}" (no initial state / no feedback) rather than an error. Returns null
 * for invalid JSON or a non-object JSON value (array, string, number...). */
function parseJsonObject(input: string): Record<string, unknown> | null {
  const trimmed = input.trim();
  if (!trimmed) return {};
  try {
    const parsed: unknown = JSON.parse(trimmed);
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      return null;
    }
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

const STATUS_COLOR: Record<string, string> = {
  completed: "bg-green-100 text-green-900",
  awaiting_approval: "bg-yellow-100 text-yellow-900",
  error: "bg-red-100 text-red-900",
};

function StatusBadge({ status }: { status: WorkflowRunStatus | string }) {
  const cls = STATUS_COLOR[status] ?? "bg-gray-100 text-gray-800";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs ${cls}`}>
      {status}
    </span>
  );
}

/** Start and drive LangGraph workflow runs for the active solution: list
 * registered workflows, run one with an optional JSON initial state, and —
 * for the most recently started run — track status and resume it past an
 * approval gate with feedback. */
export default function Workflows() {
  const workflows = useWorkflowList();
  const run = useRunWorkflow();
  const resume = useResumeWorkflow();

  const [stateInputs, setStateInputs] = useState<Record<string, string>>({});
  const [stateErrors, setStateErrors] = useState<Record<string, string>>({});
  const [feedbackInput, setFeedbackInput] = useState("");
  const [feedbackError, setFeedbackError] = useState("");

  // The most recently started/resumed run — resume.data (if a resume has
  // happened) supersedes run.data (the initial start).
  const baseRun = resume.data ?? run.data ?? null;

  // Manual refresh only — enabled is always false so this never auto-fires;
  // the "Refresh status" button calls refetch() directly (TanStack Query
  // runs the queryFn on refetch() regardless of `enabled`).
  const statusQuery = useWorkflowStatus(baseRun?.run_id ?? "", false);

  // Fold a refreshed status back into the active run. Without this, `activeRun` only ever
  // changed when a run/resume MUTATION resolved, so "Refresh status" updated the small
  // "Last checked" badge while the approval panel below — gated on
  // `activeRun.status === "awaiting_approval"` — kept rendering the stale status forever.
  // The gate would not appear when a run reached awaiting_approval, and would not clear
  // once it completed. Guarded on run_id so a stale response for a previous run can't
  // overwrite the current one.
  const activeRun =
    baseRun && statusQuery.data && statusQuery.data.run_id === baseRun.run_id
      ? { ...baseRun, ...statusQuery.data }
      : baseRun;

  const listError = workflows.error ? toDesktopError(workflows.error) : null;
  const runError = run.error ? toDesktopError(run.error) : null;
  const resumeError = resume.error ? toDesktopError(resume.error) : null;

  const handleRun = (name: string) => {
    const parsed = parseJsonObject(stateInputs[name] ?? "");
    if (parsed === null) {
      setStateErrors((prev) => ({
        ...prev,
        [name]: "Initial state must be valid JSON (an object).",
      }));
      return;
    }
    setStateErrors((prev) => ({ ...prev, [name]: "" }));
    resume.reset();
    setFeedbackInput("");
    setFeedbackError("");
    run.mutate({ workflow_name: name, state: parsed });
  };

  const handleResume = () => {
    if (!activeRun) return;
    const parsed = parseJsonObject(feedbackInput);
    if (parsed === null) {
      setFeedbackError("Feedback must be valid JSON (an object).");
      return;
    }
    setFeedbackError("");
    resume.mutate({ run_id: activeRun.run_id, feedback: parsed });
  };

  const workflowList = workflows.data?.workflows ?? [];

  return (
    <div className="p-6 space-y-4">
      <h2 className="font-semibold text-lg">Workflows</h2>
      <p className="text-sm text-slate-500">
        Start and drive LangGraph workflow runs for the active solution.
      </p>

      <ErrorBanner error={listError} />

      {workflows.isLoading && (
        <div className="text-sm text-slate-500">Loading workflows…</div>
      )}

      {!workflows.isLoading && workflowList.length === 0 && !listError && (
        <div className="rounded border border-dashed border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
          No workflows available. The active solution&apos;s orchestration
          engine may not be &quot;langgraph&quot;, or no workflows have been
          registered under its <code>workflows/</code> directory.
        </div>
      )}

      {workflowList.length > 0 && (
        <ul className="space-y-3">
          {workflowList.map((wf) => (
            <li
              key={wf.name}
              className="rounded border border-sage-100 bg-white p-4 space-y-2"
            >
              <div className="font-medium text-sm">{wf.name}</div>
              <label className="block text-xs font-medium">
                Initial state (JSON, optional)
                <textarea
                  className="mt-1 block w-full rounded border border-gray-300 p-2 font-mono text-xs"
                  rows={3}
                  placeholder="{}"
                  value={stateInputs[wf.name] ?? ""}
                  onChange={(e) =>
                    setStateInputs((prev) => ({
                      ...prev,
                      [wf.name]: e.target.value,
                    }))
                  }
                />
              </label>
              {stateErrors[wf.name] && (
                <div role="alert" className="text-xs text-red-700">
                  {stateErrors[wf.name]}
                </div>
              )}
              <button
                type="button"
                onClick={() => handleRun(wf.name)}
                disabled={run.isPending}
                className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
              >
                {run.isPending ? "Running…" : "Run"}
              </button>
            </li>
          ))}
        </ul>
      )}

      <ErrorBanner error={runError} />

      {activeRun && (
        <div className="rounded border border-sage-100 bg-white p-4 space-y-2 text-sm">
          <div className="font-medium">Run status</div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs">{activeRun.run_id}</span>
            <StatusBadge status={activeRun.status} />
          </div>

          <button
            type="button"
            onClick={() => statusQuery.refetch()}
            className="text-xs text-sage-700 underline"
          >
            Refresh status
          </button>
          {statusQuery.data && (
            <div className="text-xs text-slate-500">
              Last checked: <StatusBadge status={statusQuery.data.status} />
            </div>
          )}

          {activeRun.status === "awaiting_approval" && (
            <div className="space-y-2 border-t border-sage-100 pt-2">
              <label className="block text-xs font-medium">
                Feedback (JSON, optional)
                <textarea
                  className="mt-1 block w-full rounded border border-gray-300 p-2 font-mono text-xs"
                  rows={2}
                  placeholder='{"approved": true}'
                  value={feedbackInput}
                  onChange={(e) => setFeedbackInput(e.target.value)}
                />
              </label>
              {feedbackError && (
                <div role="alert" className="text-xs text-red-700">
                  {feedbackError}
                </div>
              )}
              <button
                type="button"
                onClick={handleResume}
                disabled={resume.isPending}
                className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
              >
                {resume.isPending ? "Resuming…" : "Resume"}
              </button>
              <ErrorBanner error={resumeError} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
