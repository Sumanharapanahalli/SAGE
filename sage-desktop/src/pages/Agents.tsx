import { useState } from "react";

import { AgentCard } from "@/components/domain/AgentCard";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useAgentPerformance, useAgents } from "@/hooks/useAgents";

export function Agents() {
  const { data, isLoading, error } = useAgents();
  const [selected, setSelected] = useState<string | null>(null);
  const performance = useAgentPerformance(selected ?? "", selected !== null);

  if (isLoading) return <p className="text-sm text-slate-500">Loading agents…</p>;
  if (error) return <ErrorBanner error={error} />;
  if (!data || data.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
        No agents configured for this solution.
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.map((a) => (
          <AgentCard
            key={a.name}
            agent={a}
            selected={selected === a.name}
            onSelect={setSelected}
          />
        ))}
      </div>
      {selected && (
        <div className="rounded-lg border border-sage-100 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-sage-900">
            Performance — {selected}
          </h3>
          {performance.isLoading && (
            <p className="text-sm text-slate-500">Loading performance…</p>
          )}
          {performance.error && <ErrorBanner error={performance.error} />}
          {performance.data && (
            <dl className="grid grid-cols-2 gap-3 text-xs text-slate-500 sm:grid-cols-4">
              <div>
                <dt className="font-medium text-slate-400">Total proposals</dt>
                <dd className="text-base text-sage-900">
                  {performance.data.total_proposals}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-400">Approved</dt>
                <dd className="text-base text-sage-900">
                  {performance.data.approved}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-400">Rejected</dt>
                <dd className="text-base text-sage-900">
                  {performance.data.rejected}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-400">Approval rate</dt>
                <dd className="text-base text-sage-900">
                  {performance.data.approval_rate === null
                    ? "No history yet"
                    : `${performance.data.approval_rate}%`}
                </dd>
              </div>
            </dl>
          )}
        </div>
      )}
    </div>
  );
}
