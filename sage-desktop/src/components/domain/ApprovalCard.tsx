import clsx from "clsx";
import { useState } from "react";

import type { Proposal, RiskClass } from "@/api/types";

interface Props {
  proposal: Proposal;
  onApprove: (trace_id: string) => void;
  onReject: (trace_id: string, feedback: string) => void;
  isPending?: boolean;
}

const RISK_STYLES: Record<RiskClass, string> = {
  INFORMATIONAL: "bg-slate-100 text-slate-700",
  EPHEMERAL: "bg-sky-100 text-sky-700",
  STATEFUL: "bg-amber-100 text-amber-700",
  EXTERNAL: "bg-violet-100 text-violet-700",
  DESTRUCTIVE: "bg-red-100 text-red-700",
};

export function ApprovalCard({
  proposal,
  onApprove,
  onReject,
  isPending = false,
}: Props) {
  const [rejecting, setRejecting] = useState(false);
  const [feedback, setFeedback] = useState("");

  const payloadJson = JSON.stringify(proposal.payload ?? {}, null, 2);
  const hasPayload = proposal.payload && Object.keys(proposal.payload).length > 0;

  return (
    <article className="rounded-lg border border-sage-100 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-center gap-2 text-xs">
        <span className="rounded bg-sage-100 px-2 py-0.5 font-mono text-sage-900">
          {proposal.action_type}
        </span>
        <span
          className={clsx(
            "rounded px-2 py-0.5 font-semibold uppercase",
            RISK_STYLES[proposal.risk_class],
          )}
        >
          {proposal.risk_class}
        </span>
        <span
          className={clsx(
            "rounded px-2 py-0.5 font-medium",
            proposal.reversible
              ? "bg-emerald-100 text-emerald-700"
              : "bg-red-100 text-red-700",
          )}
        >
          {proposal.reversible ? "Reversible" : "Irreversible"}
        </span>
        <span className="ml-auto font-mono text-slate-400">
          {proposal.trace_id}
        </span>
      </div>
      <p className="mb-3 text-sm text-sage-900">{proposal.description}</p>
      <div className="mb-3 text-xs text-slate-500">
        Proposed by <span className="font-medium">{proposal.proposed_by}</span>
        {" · "}
        {new Date(proposal.created_at).toLocaleString()}
      </div>

      {hasPayload && (
        <details className="mb-3 rounded border border-sage-100 bg-sage-50/50">
          <summary className="cursor-pointer select-none px-3 py-1.5 text-xs font-medium text-sage-700">
            Payload / details
          </summary>
          <pre className="max-h-80 overflow-auto border-t border-sage-100 px-3 py-2 text-xs text-slate-700">
            {payloadJson}
          </pre>
        </details>
      )}

      {rejecting ? (
        <div className="flex flex-col gap-2">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Why are you rejecting this? (optional, but feeds the compounding-memory signal)"
            rows={3}
            className="w-full rounded border border-sage-200 px-2 py-1.5 text-sm focus:border-sage-500 focus:outline-none"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onReject(proposal.trace_id, feedback)}
              disabled={isPending}
              className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              Confirm rejection
            </button>
            <button
              type="button"
              onClick={() => {
                setRejecting(false);
                setFeedback("");
              }}
              disabled={isPending}
              className="rounded border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onApprove(proposal.trace_id)}
            disabled={isPending}
            className="rounded bg-sage-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => setRejecting(true)}
            disabled={isPending}
            className="rounded border border-red-200 bg-white px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      )}
    </article>
  );
}
