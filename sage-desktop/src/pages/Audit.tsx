import { useState } from "react";

import { AuditTable } from "@/components/domain/AuditTable";
import { AuditTraceDetail } from "@/components/domain/AuditTraceDetail";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useAuditEvents, useAuditStats } from "@/hooks/useAudit";

const PAGE_SIZE = 50;

export function Audit() {
  const [actionType, setActionType] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedTrace, setSelectedTrace] = useState<string | null>(null);

  const stats = useAuditStats();
  const { data, isLoading, error } = useAuditEvents({
    ...(actionType ? { action_type: actionType } : {}),
    limit: PAGE_SIZE,
    offset,
  });

  const total = data?.total ?? 0;
  const knownActionTypes = Object.keys(stats.data?.by_action_type ?? {}).sort();

  if (selectedTrace) {
    return (
      <AuditTraceDetail
        trace_id={selectedTrace}
        onClose={() => setSelectedTrace(null)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs font-medium uppercase text-slate-500">
          Action type
        </label>
        <select
          value={actionType}
          onChange={(e) => {
            setActionType(e.target.value);
            setOffset(0);
          }}
          className="w-60 rounded border border-sage-100 bg-white px-2 py-1 text-sm"
        >
          <option value="">All action types</option>
          {knownActionTypes.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          <span>
            {total === 0
              ? "0"
              : `${offset + 1}–${Math.min(offset + PAGE_SIZE, total)} of ${total}`}
          </span>
          <button
            type="button"
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            disabled={offset === 0}
            className="rounded border border-sage-100 px-2 py-1 disabled:opacity-40"
          >
            Prev
          </button>
          <button
            type="button"
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
            disabled={offset + PAGE_SIZE >= total}
            className="rounded border border-sage-100 px-2 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>

      <ErrorBanner error={error ?? null} />
      {isLoading ? (
        <p className="text-sm text-slate-500">Loading events…</p>
      ) : (
        <AuditTable
          events={data?.events ?? []}
          onTraceClick={setSelectedTrace}
        />
      )}
    </div>
  );
}
