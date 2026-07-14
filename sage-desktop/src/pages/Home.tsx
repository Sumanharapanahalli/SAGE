import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { toDesktopError } from "@/api/client";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { RemoveSolutionDialog } from "@/components/domain/RemoveSolutionDialog";
import { getLastSolution, setLastSolution } from "@/lib/lastSolution";
import {
  useCurrentSolution,
  useRemoveSolution,
  useSolutions,
  useSwitchSolution,
} from "@/hooks/useSolutions";
import type { RemoveSolutionMode, SolutionRef } from "@/api/types";

const DEFAULT_LANDING = "/approvals";

export default function Home() {
  const navigate = useNavigate();
  const current = useCurrentSolution();
  const solutions = useSolutions();
  const switchSolution = useSwitchSolution();
  const removeSolution = useRemoveSolution();
  const [filter, setFilter] = useState("");
  // Name of the solution whose remove-confirmation panel is open (one at a time).
  const [removing, setRemoving] = useState<string | null>(null);
  const triedAutoLoad = useRef(false);

  // Auto-reopen the last used solution once, only if none is active yet.
  useEffect(() => {
    if (triedAutoLoad.current) return;
    if (current.isLoading) return;
    if (current.data) return;
    const last = getLastSolution();
    if (!last) return;
    triedAutoLoad.current = true;
    switchSolution.mutate({ name: last.name, path: last.path });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [current.isLoading, current.data]);

  // Leave Home once a switch (auto or manual) succeeds.
  useEffect(() => {
    if (switchSolution.isSuccess && switchSolution.data) {
      setLastSolution({
        name: switchSolution.data.name,
        path: switchSolution.data.path,
      });
      navigate(DEFAULT_LANDING, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [switchSolution.isSuccess, switchSolution.data]);

  const handlePick = (s: SolutionRef) => {
    switchSolution.mutate({ name: s.name, path: s.path });
  };

  const handleRemove = (
    s: SolutionRef,
    mode: RemoveSolutionMode,
    confirm?: string,
  ) => {
    removeSolution.mutate(
      { name: s.name, mode, confirm },
      { onSuccess: () => setRemoving(null) },
    );
  };

  const filtered = (solutions.data ?? []).filter((s) =>
    s.name.toLowerCase().includes(filter.toLowerCase()),
  );

  if (triedAutoLoad.current && switchSolution.isPending) {
    const last = getLastSolution();
    return (
      <div className="p-6 text-sm text-slate-500">
        Reopening {last?.name ?? "your last solution"}…
      </div>
    );
  }

  const loadError =
    solutions.error ??
    (switchSolution.error ? toDesktopError(switchSolution.error) : null);
  // The list could not be loaded at all. Distinct from "loaded, and it is empty".
  const listUnavailable = Boolean(solutions.error) || !solutions.data;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <ErrorBanner error={loadError} />

      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter solutions…"
        className="w-full rounded border border-sage-300 px-3 py-2 text-sm placeholder:text-slate-700"
      />

      {solutions.isLoading ? (
        <div aria-busy="true" aria-live="polite" className="flex flex-col gap-2">
          <span className="sr-only">Loading solutions…</span>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="h-14 animate-pulse rounded border border-sage-300 bg-sage-100"
            />
          ))}
        </div>
      ) : listUnavailable ? null /* the ErrorBanner above already says why; an empty-state
            next to a connection error is contradictory — a live run showed "Sidecar
            disconnected" and "No solutions match your filter." stacked together. */
      : filtered.length === 0 ? (
        <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-700">
          {solutions.data.length === 0
            ? "No solutions yet — create one to get started."
            : "No solutions match your filter."}
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {filtered.map((s) => (
            <li key={s.path}>
              <div className="flex items-start gap-2">
                <button
                  type="button"
                  onClick={() => handlePick(s)}
                  disabled={switchSolution.isPending}
                  className="flex flex-1 flex-col items-start rounded border border-sage-100 bg-white p-3 text-left hover:border-sage-300 hover:bg-sage-50 disabled:opacity-50"
                >
                  <span className="font-medium text-sage-900">{s.name}</span>
                  <span className="text-xs text-slate-600">{s.path}</span>
                  {s.has_sage_dir && (
                    <span className="mt-1 inline-block rounded bg-sage-100 px-1.5 py-0.5 text-[11px] text-sage-700">
                      has data
                    </span>
                  )}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setRemoving((cur) => (cur === s.name ? null : s.name))
                  }
                  disabled={switchSolution.isPending}
                  aria-label={`Remove ${s.name}`}
                  className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-600 hover:border-red-300 hover:text-red-700 disabled:opacity-50"
                >
                  Remove
                </button>
              </div>
              {removing === s.name && (
                <RemoveSolutionDialog
                  solution={s}
                  isPending={removeSolution.isPending}
                  error={removeSolution.error ?? null}
                  onCancel={() => setRemoving(null)}
                  onConfirm={(mode, confirm) => handleRemove(s, mode, confirm)}
                />
              )}
            </li>
          ))}
        </ul>
      )}

      {/* A solid primary button. A DASHED border reads as a dropzone or a placeholder, not
          as the main call to action on the page whose whole job is picking or creating a
          solution. */}
      <Link
        to="/onboarding"
        className="inline-flex w-fit items-center rounded bg-sage-700 px-4 py-2 text-sm font-medium text-white hover:bg-sage-800"
      >
        + New solution
      </Link>
    </div>
  );
}
