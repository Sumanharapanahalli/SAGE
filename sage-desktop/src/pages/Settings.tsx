import { useLlmInfo, useSwitchLlm } from "@/hooks/useLlm";
import {
  useCurrentSolution,
  useSolutions,
  useSwitchSolution,
} from "@/hooks/useSolutions";
import { LlmProviderForm } from "@/components/domain/LlmProviderForm";
import { SolutionPicker } from "@/components/domain/SolutionPicker";
import { TelemetryPanel } from "@/components/domain/TelemetryPanel";
import { UpdatePanel } from "@/components/domain/UpdatePanel";

export default function Settings() {
  const info = useLlmInfo();
  const switcher = useSwitchLlm();

  const solutions = useSolutions();
  const currentSolution = useCurrentSolution();
  const solutionSwitcher = useSwitchSolution();

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

      <section id="updates" className="rounded border border-gray-200 p-4">
        <h2 className="mb-2 font-semibold">Application updates</h2>
        <p className="mb-3 text-sm text-gray-600">
          Checks GitHub Releases for a newer signed SAGE Desktop build.
        </p>
        <UpdatePanel />
      </section>

      <section id="telemetry" className="rounded border border-gray-200 p-4">
        <h2 className="mb-2 font-semibold">Telemetry</h2>
        <TelemetryPanel />
      </section>
    </div>
  );
}
