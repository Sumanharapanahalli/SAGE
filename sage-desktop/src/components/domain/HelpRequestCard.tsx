import { useState } from "react";

import type { HelpRequest, HelpRequestUrgency } from "@/api/types";

interface Props {
  request: HelpRequest;
  onClaim: (id: string) => void;
  onRespond: (id: string) => void;
  onClose: (id: string) => void;
}

const URGENCY_STYLE: Record<HelpRequestUrgency, string> = {
  low: "bg-slate-100 text-slate-700",
  medium: "bg-sky-100 text-sky-800",
  high: "bg-amber-100 text-amber-800",
  critical: "bg-rose-100 text-rose-800",
};

export function HelpRequestCard({
  request,
  onClaim,
  onRespond,
  onClose,
}: Props) {
  const [confirmClose, setConfirmClose] = useState(false);

  return (
    <article className="space-y-2 rounded border border-slate-200 bg-white p-3">
      <header className="flex items-baseline justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">
            {request.title}
          </h3>
          <div className="text-xs text-slate-500">
            {request.requester_agent} @ {request.requester_solution}
          </div>
        </div>
        <span
          className={`rounded px-1.5 py-0.5 text-xs font-mono ${URGENCY_STYLE[request.urgency]}`}
        >
          {request.urgency.toUpperCase()}
        </span>
      </header>
      <div className="flex flex-wrap gap-1">
        {request.required_expertise.map((e) => (
          <span
            key={e}
            className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-700"
          >
            {e}
          </span>
        ))}
      </div>
      {request.context && (
        <p className="whitespace-pre-wrap text-sm text-slate-700">
          {request.context}
        </p>
      )}
      {request.claimed_by && (
        <div className="text-xs text-slate-500">
          Claimed by {request.claimed_by.agent} @ {request.claimed_by.solution}
        </div>
      )}
      {request.responses.length > 0 && (
        <div className="space-y-1 rounded bg-slate-50 p-2 text-xs">
          <div className="font-semibold text-slate-700">
            Responses ({request.responses.length})
          </div>
          {request.responses.map((r, i) => (
            <div key={i}>
              <span className="font-mono">
                {r.responder_agent} @ {r.responder_solution}
              </span>
              : {r.content}
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
          onClick={() => onClaim(request.id)}
          disabled={!!request.claimed_by || request.status !== "open"}
        >
          Claim
        </button>
        <button
          type="button"
          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50"
          onClick={() => onRespond(request.id)}
        >
          Respond
        </button>
        {!confirmClose ? (
          <button
            type="button"
            className="rounded border border-rose-300 bg-white px-2 py-1 text-xs text-rose-700 hover:bg-rose-50 disabled:opacity-50"
            onClick={() => setConfirmClose(true)}
            disabled={request.status === "closed"}
          >
            Close
          </button>
        ) : (
          <button
            type="button"
            className="rounded bg-rose-600 px-2 py-1 text-xs text-white hover:bg-rose-700"
            onClick={() => {
              onClose(request.id);
              setConfirmClose(false);
            }}
          >
            Confirm close
          </button>
        )}
      </div>
    </article>
  );
}
