import { useState } from "react";
import { Link } from "react-router-dom";

import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { toDesktopError } from "@/api/client";
import { useAnalyzeLog } from "@/hooks/useAnalyze";

/** The desktop operator's SURFACE -> PROPOSE trigger: paste a log/signal,
 * run it through the AnalystAgent, and the result becomes a real pending
 * proposal — visible immediately in Approvals. */
export default function Analyze() {
  const [logEntry, setLogEntry] = useState("");
  const analyze = useAnalyzeLog();

  const handleSubmit = () => {
    if (!logEntry.trim()) return;
    analyze.mutate({ log_entry: logEntry });
  };

  const error = analyze.error ? toDesktopError(analyze.error) : null;
  const proposal = analyze.data;

  return (
    <div className="p-6">
      {/* A plain button rather than a <form onSubmit> — the field is a
          multi-line textarea where Enter should insert a newline, not
          submit. */}
      <div className="mb-6 space-y-3 rounded border border-gray-200 p-4">
        <h2 className="font-semibold">Analyze a log / signal</h2>
        <label className="block">
          <span className="block text-sm font-medium">Log entry</span>
          <textarea
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            rows={4}
            value={logEntry}
            onChange={(e) => setLogEntry(e.target.value)}
            placeholder="Paste a log line, error, or signal to analyze…"
          />
        </label>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={analyze.isPending}
          className="rounded bg-sage-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        >
          {analyze.isPending ? "Analyzing…" : "Analyze"}
        </button>
      </div>

      <ErrorBanner error={error} />

      {proposal && (
        <div className="rounded border border-sage-100 bg-white p-4">
          <div className="text-sm font-medium">{proposal.description}</div>
          <div className="mt-1 text-xs text-slate-500">
            trace_id: {proposal.trace_id}
          </div>
          <Link
            to="/approvals"
            className="mt-2 inline-block text-sm text-sage-600 underline-offset-2 hover:underline"
          >
            View in Approvals
          </Link>
        </div>
      )}
    </div>
  );
}
