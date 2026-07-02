import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { toDesktopError } from "@/api/client";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { getLastSolution, setLastSolution } from "@/lib/lastSolution";
import {
  useCurrentSolution,
  useSolutions,
  useSwitchSolution,
} from "@/hooks/useSolutions";
import type { SolutionRef } from "@/api/types";

const DEFAULT_LANDING = "/approvals";

export default function Home() {
  const navigate = useNavigate();
  const current = useCurrentSolution();
  const solutions = useSolutions();
  const switchSolution = useSwitchSolution();
  const [filter, setFilter] = useState("");
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

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <ErrorBanner
        error={
          solutions.error ??
          (switchSolution.error ? toDesktopError(switchSolution.error) : null)
        }
      />

      <input
        type="text"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter solutions…"
        className="w-full rounded border border-sage-100 px-3 py-2 text-sm"
      />

      {solutions.isLoading ? (
        <p className="text-sm text-slate-500">Loading solutions…</p>
      ) : filtered.length === 0 ? (
        <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
          {solutions.data?.length === 0
            ? "No solutions found."
            : "No solutions match your filter."}
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {filtered.map((s) => (
            <li key={s.path}>
              <button
                type="button"
                onClick={() => handlePick(s)}
                disabled={switchSolution.isPending}
                className="flex w-full flex-col items-start rounded border border-sage-100 bg-white p-3 text-left hover:border-sage-300 hover:bg-sage-50 disabled:opacity-50"
              >
                <span className="font-medium text-sage-900">{s.name}</span>
                <span className="text-xs text-slate-500">{s.path}</span>
                {s.has_sage_dir && (
                  <span className="mt-1 inline-block rounded bg-sage-100 px-1.5 py-0.5 text-[11px] text-sage-700">
                    has data
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      <Link
        to="/onboarding"
        className="block rounded border border-dashed border-sage-400 px-3 py-2 text-center text-sm text-sage-700 hover:bg-sage-100"
      >
        + New solution
      </Link>
    </div>
  );
}
