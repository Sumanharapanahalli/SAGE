import { useState } from "react";

import type {
  ApproveBuildParams,
  BuildRunDetail,
  DesktopError,
} from "@/api/types";

interface Props {
  detail: BuildRunDetail;
  isApproving: boolean;
  approveError: DesktopError | null;
  onApprove: (p: ApproveBuildParams) => void;
}

function approveLabel(state: string): string | null {
  if (state === "awaiting_plan") return "Approve plan";
  if (state === "awaiting_build") return "Approve build";
  return null;
}

function errorMessage(error: DesktopError): string {
  if (error.kind === "InvalidParams" || error.kind === "SidecarDown") {
    return `${error.kind}: ${error.detail.message}`;
  }
  return `Approval failed (${error.kind}).`;
}

export function BuildRunDetailView({
  detail,
  isApproving,
  approveError,
  onApprove,
}: Props) {
  const [feedback, setFeedback] = useState("");
  const label = approveLabel(detail.state);
  const showApprovalControls = label !== null;
  const trimmedFeedback = feedback.trim();

  return (
    <div className="space-y-4">
      <div className="rounded border border-sage-100 bg-white p-4 text-sm">
        <div className="flex items-baseline justify-between">
          <h3 className="font-semibold">{detail.run_id}</h3>
          <span className="font-mono text-xs text-slate-500">
            {detail.state}
          </span>
        </div>
        <p className="mt-1 text-slate-600">{detail.state_description}</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-600">
          <div>
            <span className="font-semibold">Solution:</span>{" "}
            {detail.solution_name || "—"}
          </div>
          <div>
            <span className="font-semibold">HITL:</span> {detail.hitl_level}
          </div>
          <div>
            <span className="font-semibold">Created:</span>{" "}
            {new Date(detail.created_at).toLocaleString()}
          </div>
          <div>
            <span className="font-semibold">Updated:</span>{" "}
            {new Date(detail.updated_at).toLocaleString()}
          </div>
        </div>
        <p className="mt-3 text-sm">
          <span className="font-semibold">Description:</span>{" "}
          {detail.product_description}
        </p>
        {detail.error && (
          <div className="mt-3 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-900">
            {detail.error}
          </div>
        )}
      </div>

      {detail.plan.length > 0 && (
        <div className="rounded border border-sage-100 bg-white p-4">
          <h4 className="text-sm font-semibold">Plan ({detail.task_count})</h4>
          <ul className="mt-2 space-y-1 text-xs text-slate-700">
            {detail.plan.map((task, idx) => {
              const t = task as Record<string, unknown>;
              return (
                <li key={idx}>
                  <span className="font-mono">{String(t.task_type ?? "")}</span>
                  {t.description ? ` — ${String(t.description)}` : ""}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {detail.agent_results.length > 0 && (
        <div className="rounded border border-sage-100 bg-white p-4">
          <h4 className="text-sm font-semibold">Agent results</h4>
          <ul className="mt-2 space-y-1 text-xs text-slate-700">
            {detail.agent_results.map((r, idx) => (
              <li key={idx}>
                <span className="font-mono">[{r.agent_role || "agent"}]</span>{" "}
                {r.task_type} — {r.status}
                {r.error ? (
                  <span className="text-red-700"> ({r.error})</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}

      {detail.critic_scores.length > 0 && (
        <div className="rounded border border-sage-100 bg-white p-4">
          <h4 className="text-sm font-semibold">Critic scores</h4>
          <ul className="mt-2 space-y-1 text-xs text-slate-700">
            {detail.critic_scores.map((s, idx) => (
              <li key={idx}>
                {s.phase}: {s.score}{" "}
                <span
                  className={s.passed ? "text-green-700" : "text-red-700"}
                >
                  {s.passed ? "✓" : "✗"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {showApprovalControls && (
        <div className="rounded border border-sage-100 bg-white p-4">
          <label className="block" htmlFor="build-feedback">
            <span className="block text-sm font-medium">
              Feedback (optional)
            </span>
            <textarea
              id="build-feedback"
              className="mt-1 block w-full rounded border border-gray-300 p-2"
              rows={2}
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
            />
          </label>
          {approveError && (
            <div
              role="alert"
              className="mt-2 rounded border border-red-200 bg-red-50 p-2 text-xs text-red-900"
            >
              {errorMessage(approveError)}
            </div>
          )}
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              disabled={isApproving}
              className="rounded bg-sage-600 px-4 py-2 text-sm text-white hover:bg-sage-700 disabled:opacity-50"
              onClick={() =>
                onApprove({
                  run_id: detail.run_id,
                  approved: true,
                  feedback: trimmedFeedback,
                })
              }
            >
              {label}
            </button>
            <button
              type="button"
              disabled={isApproving}
              className="rounded border border-red-400 px-4 py-2 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
              onClick={() =>
                onApprove({
                  run_id: detail.run_id,
                  approved: false,
                  feedback: trimmedFeedback,
                })
              }
            >
              Reject
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
