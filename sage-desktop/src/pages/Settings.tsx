import { useLlmInfo, useSwitchLlm } from "@/hooks/useLlm";
import { LlmProviderForm } from "@/components/domain/LlmProviderForm";

export default function Settings() {
  const info = useLlmInfo();
  const switcher = useSwitchLlm();

  if (info.isLoading) return <div className="p-6">Loading…</div>;
  if (info.isError) return <div className="p-6 text-red-700">Failed to load LLM info.</div>;
  const current = info.data!;

  return (
    <div className="mx-auto max-w-xl space-y-6 p-6">
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
