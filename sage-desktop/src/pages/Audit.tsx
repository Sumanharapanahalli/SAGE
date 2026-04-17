import { useState } from "react";

import { AuditTable } from "@/components/domain/AuditTable";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useAuditEvents } from "@/hooks/useAudit";

export function Audit() {
  const [actionType, setActionType] = useState("");
  const { data, isLoading, error } = useAuditEvents(
    actionType ? { action_type: actionType, limit: 100 } : { limit: 100 },
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <label className="text-xs font-medium uppercase text-slate-500">
          Action type
        </label>
        <input
          type="text"
          value={actionType}
          onChange={(e) => setActionType(e.target.value)}
          placeholder="e.g. yaml_edit"
          className="w-60 rounded border border-sage-100 bg-white px-2 py-1 text-sm"
        />
      </div>
      <ErrorBanner error={error ?? null} />
      {isLoading ? (
        <p className="text-sm text-slate-500">Loading events…</p>
      ) : (
        <AuditTable events={data?.events ?? []} />
      )}
    </div>
  );
}
