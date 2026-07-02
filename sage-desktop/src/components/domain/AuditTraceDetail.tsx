import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useAuditByTrace } from "@/hooks/useAudit";

interface Props {
  trace_id: string;
  onClose: () => void;
}

/**
 * Full chronological drill-down for a single trace_id — the compliance story
 * ("show me every step of this decision"). Reads the previously-unused
 * useAuditByTrace hook.
 */
export function AuditTraceDetail({ trace_id, onClose }: Props) {
  const { data, isLoading, error } = useAuditByTrace(trace_id);

  return (
    <div className="rounded-lg border border-sage-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-sm font-semibold text-sage-900">
          Trace <span className="font-mono">{trace_id}</span>
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="ml-auto rounded border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
        >
          Back to log
        </button>
      </div>

      <ErrorBanner error={error ?? null} />

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading trace…</p>
      ) : !data || data.events.length === 0 ? (
        <p className="text-sm text-slate-500">No events for this trace.</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {data.events.map((e, i) => (
            <li
              key={e.id}
              className="rounded border border-sage-100 bg-sage-50/40 p-3"
            >
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="rounded bg-sage-100 px-1.5 py-0.5 font-mono text-sage-900">
                  {i + 1}
                </span>
                <span className="font-medium text-sage-900">
                  {e.action_type}
                </span>
                <span>· {e.actor}</span>
                {e.status && <span>· {e.status}</span>}
                <span className="ml-auto font-mono">
                  {new Date(e.timestamp).toLocaleString()}
                </span>
              </div>
              {e.input_context && (
                <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-white px-2 py-1 text-xs text-slate-700">
                  {e.input_context}
                </pre>
              )}
              {e.output_content && (
                <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-white px-2 py-1 text-xs text-slate-700">
                  {e.output_content}
                </pre>
              )}
              {e.approved_by && (
                <div className="mt-1 text-xs text-emerald-700">
                  Approved by {e.approved_by}
                  {e.approver_role ? ` (${e.approver_role})` : ""}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
