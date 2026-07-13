import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useLlmInfo, useSwitchLlm } from "@/hooks/useLlm";
import {
  useCurrentSolution,
  useSolutions,
  useSwitchSolution,
  useUnloadSolution,
} from "@/hooks/useSolutions";
import { LlmProviderForm } from "@/components/domain/LlmProviderForm";
import { SolutionPicker } from "@/components/domain/SolutionPicker";

export default function Settings() {
  const navigate = useNavigate();
  const info = useLlmInfo();
  const switcher = useSwitchLlm();

  const solutions = useSolutions();
  const currentSolution = useCurrentSolution();
  const solutionSwitcher = useSwitchSolution();
  const unloader = useUnloadSolution();

  // Once the sidecar has respawned with no solution, the only meaningful
  // place to be is the picker.
  useEffect(() => {
    if (unloader.isSuccess) {
      navigate("/", { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unloader.isSuccess]);

  if (info.isLoading) return <div className="p-6">Loading…</div>;
  if (info.isError) return <div className="p-6 text-red-700">Failed to load LLM info.</div>;
  const current = info.data!;

  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
      <section id="solution" className="rounded border border-gray-200 p-4">
        <h2 className="mb-2 font-semibold">Active solution</h2>
        <p className="mb-3 text-sm text-gray-600">
          Switching will respawn the sidecar against the chosen solution.
        </p>
        <SolutionPicker
          solutions={solutions.data ?? []}
          current={currentSolution.data ?? null}
          isLoading={solutions.isLoading || currentSolution.isLoading}
          isSwitching={solutionSwitcher.isPending}
          switchError={solutionSwitcher.error ?? null}
          onSwitch={(s) => solutionSwitcher.mutate({ name: s.name, path: s.path })}
        />
        {solutionSwitcher.isSuccess && (
          <p className="mt-2 text-sm text-green-700">
            Switched to {solutionSwitcher.data.name}.
          </p>
        )}

        <div className="mt-4 border-t border-gray-200 pt-3">
          <p className="mb-2 text-sm text-gray-600">
            Unloading closes the active solution and returns you to the picker.
            Nothing on disk is touched — the sidecar simply respawns with no
            solution attached.
          </p>
          <button
            type="button"
            onClick={() => unloader.mutate()}
            disabled={unloader.isPending || !currentSolution.data}
            className="rounded border border-gray-300 px-3 py-1 text-sm text-gray-800 hover:border-red-300 hover:text-red-700 disabled:opacity-50"
          >
            {unloader.isPending ? "Unloading…" : "Unload solution"}
          </button>
          {unloader.isError && (
            <p className="mt-2 text-sm text-red-700" role="alert">
              Unload failed ({unloader.error.kind}).
            </p>
          )}
        </div>
      </section>

      <section className="rounded border border-gray-200 p-4">
        <h2 className="mb-2 font-semibold">Current LLM</h2>
        <p className="text-sm">Provider: <span className="font-mono">{current.provider_name}</span></p>
        <p className="text-sm">Model: <span className="font-mono">{current.model || "(default)"}</span></p>
      </section>
      <section className="rounded border border-gray-200 p-4">
        <h2 className="mb-4 font-semibold">Switch LLM</h2>
        <LlmProviderForm
          current={current}
          isPending={switcher.isPending}
          onSubmit={(req) => switcher.mutate(req)}
        />
        {switcher.isSuccess && (
          <p className="mt-2 text-sm text-green-700">
            Switched to {switcher.data.provider_name}
            {switcher.data.saved_as_default ? " (saved as default)" : ""}.
          </p>
        )}
        {switcher.isError && (
          <p className="mt-2 text-sm text-red-700">Switch failed.</p>
        )}
      </section>
    </div>
  );
}
