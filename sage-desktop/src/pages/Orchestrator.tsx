import { useState } from "react";

import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useOrchestratorRecent,
  useOrchestratorStats,
} from "@/hooks/useOrchestrator";

/**
 * Observability over the 9 orchestrator-intelligence modules.
 *
 * Read-only, matching what the web page actually consumes. Modules that could
 * not be loaded are labelled "not active" rather than shown as zeroes — on a
 * desktop install these subsystems are legitimately often idle, and a row of
 * zeroes would read as "ran, did nothing".
 */

const MODULES = [
  { id: "events", label: "Event bus", hasRecent: true },
  { id: "budget", label: "Budget", hasRecent: false },
  { id: "reflection", label: "Reflection", hasRecent: true },
  { id: "plans", label: "Beam search / plans", hasRecent: true },
  { id: "spawns", label: "Agent spawner", hasRecent: true },
  { id: "tools", label: "Tools", hasRecent: true },
  { id: "backtrack", label: "Backtrack", hasRecent: true },
  { id: "consensus", label: "Consensus", hasRecent: true },
  { id: "memory_planner", label: "Memory planner", hasRecent: false },
] as const;

export default function Orchestrator() {
  const stats = useOrchestratorStats();
  const [selected, setSelected] = useState<string | null>(null);
  const recent = useOrchestratorRecent(selected ?? "");

  const unavailable = new Set(stats.data?.unavailable ?? []);

  return (
    <div className="space-y-4 p-6">
      <p className="text-sm text-sage-700">
        Live counters from the nine orchestrator-intelligence modules.
      </p>

      <ErrorBanner error={stats.error} />
      {stats.isLoading && (
        <p className="text-sm text-slate-500">Loading orchestrator stats…</p>
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {MODULES.map((m) => {
          const values = stats.data?.modules?.[m.id] ?? {};
          const inactive = unavailable.has(m.id);
          return (
            <div
              key={m.id}
              className="rounded border border-sage-100 bg-white p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-sage-900">
                  {m.label}
                </span>
                {m.hasRecent && !inactive && (
                  <button
                    className="text-xs text-sage-700 hover:underline"
                    onClick={() =>
                      setSelected(selected === m.id ? null : m.id)
                    }
                  >
                    {selected === m.id ? "Hide" : "Recent"}
                  </button>
                )}
              </div>

              {inactive ? (
                <div className="mt-1 text-xs text-slate-500">Not active</div>
              ) : (
                <dl className="mt-2 space-y-0.5 text-xs text-sage-700">
                  {Object.entries(values).length === 0 && (
                    <div className="text-slate-500">No activity yet</div>
                  )}
                  {Object.entries(values).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-2">
                      <dt className="text-slate-400">{k}</dt>
                      <dd className="text-sage-900">{String(v)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          );
        })}
      </div>

      {selected && (
        <div className="rounded border border-sage-100 bg-white p-4">
          <div className="mb-2 text-sm font-medium text-sage-900">
            Recent — {MODULES.find((m) => m.id === selected)?.label}
          </div>
          <ErrorBanner error={recent.error} />
          {recent.data && !recent.data.available && (
            <div className="text-sm text-slate-500">Not active.</div>
          )}
          {recent.data?.available && recent.data.items.length === 0 && (
            <div className="text-sm text-slate-500">Nothing recorded yet.</div>
          )}
          {recent.data?.items.map((item, i) => (
            <pre
              key={i}
              className="mt-1 overflow-x-auto rounded bg-sage-50 p-2 text-xs"
            >
              {JSON.stringify(item, null, 2)}
            </pre>
          ))}
        </div>
      )}
    </div>
  );
}
