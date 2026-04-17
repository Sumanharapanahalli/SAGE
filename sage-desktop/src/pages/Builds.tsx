import { useState } from "react";

import { BuildRunDetailView } from "@/components/domain/BuildRunDetailView";
import { BuildRunsTable } from "@/components/domain/BuildRunsTable";
import { StartBuildForm } from "@/components/domain/StartBuildForm";
import {
  useApproveBuildStage,
  useBuild,
  useBuilds,
  useStartBuild,
} from "@/hooks/useBuilds";

export default function Builds() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const list = useBuilds();
  const detail = useBuild(selectedId ?? undefined);
  const start = useStartBuild();
  const approve = useApproveBuildStage();

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <div className="flex items-baseline justify-between">
        <div>
          <h2 className="text-lg font-semibold">Builds</h2>
          <p className="text-sm text-gray-600">
            Kick off and review build orchestrator runs for the active
            solution.
          </p>
        </div>
        <button
          type="button"
          className="rounded bg-sage-600 px-4 py-2 text-sm text-white hover:bg-sage-700"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? "Close" : "Start new build"}
        </button>
      </div>

      {showForm && (
        <div className="rounded border border-sage-100 bg-white p-4">
          <StartBuildForm
            isPending={start.isPending}
            error={start.error ?? null}
            onStart={(p) =>
              start.mutate(p, {
                onSuccess: (data) => {
                  setSelectedId(data.run_id);
                  setShowForm(false);
                },
              })
            }
          />
        </div>
      )}

      {list.isError && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          Could not load build runs: {list.error?.kind ?? "unknown error"}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <BuildRunsTable
            runs={list.data ?? []}
            selectedId={selectedId}
            onSelect={(id) => setSelectedId(id)}
          />
        </div>
        <div>
          {selectedId ? (
            detail.isLoading ? (
              <div className="rounded border border-sage-100 bg-white p-6 text-sm text-slate-500">
                Loading run…
              </div>
            ) : detail.data ? (
              <BuildRunDetailView
                detail={detail.data}
                isApproving={approve.isPending}
                approveError={approve.error ?? null}
                onApprove={(p) => approve.mutate(p)}
              />
            ) : (
              <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-900">
                Run details unavailable: {detail.error?.kind ?? "unknown"}
              </div>
            )
          ) : (
            <div className="rounded border border-sage-100 bg-white p-6 text-sm text-slate-500">
              Select a run to see details, critic scores, and approval gates.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
