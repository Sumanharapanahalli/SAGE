import { Link } from "react-router-dom";

import { toDesktopError } from "@/api/client";
import type { FeatureRequest, FeatureRequestAction, PlanResult } from "@/api/types";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { usePlanFeatureRequest } from "@/hooks/useBacklog";

const PRIORITY_STYLES: Record<FeatureRequest["priority"], string> = {
  low: "bg-gray-100 text-gray-800",
  medium: "bg-blue-100 text-blue-800",
  high: "bg-amber-100 text-amber-800",
  critical: "bg-red-100 text-red-800",
};

const STATUS_STYLES: Record<FeatureRequest["status"], string> = {
  pending: "bg-yellow-100 text-yellow-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-gray-100 text-gray-800",
  completed: "bg-emerald-100 text-emerald-800",
  in_progress: "bg-indigo-100 text-indigo-800",
  in_planning: "bg-purple-100 text-purple-800",
  github_pr: "bg-sky-100 text-sky-800",
};

// Generating a plan only makes sense before one has been requested — hide
// the action once a request is already in_planning, has gone to github_pr,
// or is rejected/completed (mirrors web's Improvements.tsx gating).
const PLANNABLE_STATUSES: ReadonlyArray<FeatureRequest["status"]> = [
  "pending",
  "approved",
];

function isGithubPlanResult(
  result: PlanResult,
): result is Extract<PlanResult, { status: "github_pr" }> {
  return result.status === "github_pr";
}

interface Props {
  item: FeatureRequest;
  onAction: (id: string, action: FeatureRequestAction) => void;
  isPending: boolean;
}

export function FeatureRequestRow({ item, onAction, isPending }: Props) {
  const plan = usePlanFeatureRequest();
  const planError = plan.error ? toDesktopError(plan.error) : null;

  return (
    <article className="rounded border border-gray-200 p-4">
      <header className="flex items-center justify-between">
        <h3 className="font-semibold">{item.title}</h3>
        <div className="flex gap-2 text-xs">
          <span className={`rounded px-2 py-0.5 ${PRIORITY_STYLES[item.priority]}`}>
            {item.priority}
          </span>
          <span className={`rounded px-2 py-0.5 ${STATUS_STYLES[item.status]}`}>
            {item.status}
          </span>
        </div>
      </header>
      <p className="mt-2 text-sm text-gray-700">{item.description}</p>
      <p className="mt-2 text-xs text-gray-500">
        by {item.requested_by} · {item.scope}
      </p>
      {item.status === "pending" && (
        <div className="mt-3 flex gap-2">
          <button
            disabled={isPending}
            onClick={() => onAction(item.id, "approve")}
            className="rounded bg-green-600 px-3 py-1 text-xs text-white disabled:opacity-50"
          >
            Approve
          </button>
          <button
            disabled={isPending}
            onClick={() => onAction(item.id, "reject")}
            className="rounded bg-gray-600 px-3 py-1 text-xs text-white disabled:opacity-50"
          >
            Reject
          </button>
          <button
            disabled={isPending}
            onClick={() => onAction(item.id, "complete")}
            className="rounded bg-emerald-600 px-3 py-1 text-xs text-white disabled:opacity-50"
          >
            Complete
          </button>
        </div>
      )}
      {PLANNABLE_STATUSES.includes(item.status) && (
        <div className="mt-3">
          <button
            disabled={plan.isPending}
            onClick={() => plan.mutate(item.id)}
            className="rounded bg-purple-600 px-3 py-1 text-xs text-white disabled:opacity-50"
          >
            {plan.isPending ? "Generating plan…" : "Generate Plan"}
          </button>
        </div>
      )}
      {planError && (
        <div className="mt-2">
          <ErrorBanner error={planError} />
        </div>
      )}
      {plan.data && (
        <div className="mt-2 text-xs">
          {isGithubPlanResult(plan.data) ? (
            <a
              href={plan.data.github_issue_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sage-600 underline-offset-2 hover:underline"
            >
              Open GitHub issue
            </a>
          ) : (
            <span>
              Plan created — see{" "}
              <Link
                to="/approvals"
                className="text-sage-600 underline-offset-2 hover:underline"
              >
                Approvals
              </Link>
            </span>
          )}
        </div>
      )}
    </article>
  );
}
