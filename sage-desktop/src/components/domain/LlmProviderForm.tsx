import { useState } from "react";
import type { LlmInfo } from "@/api/types";

interface Props {
  current: LlmInfo;
  onSubmit: (req: { provider: string; model: string; save_as_default: boolean }) => void;
  isPending: boolean;
}

export function LlmProviderForm({ current, onSubmit, isPending }: Props) {
  const providers = current.available_providers.length > 0
    ? current.available_providers
    : [current.provider_name];
  const [provider, setProvider] = useState(providers[0]);
  const [model, setModel] = useState(current.model);
  const [saveAsDefault, setSaveAsDefault] = useState(false);
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ provider, model, save_as_default: saveAsDefault });
      }}
    >
      <label className="block">
        <span className="block text-sm font-medium">Provider</span>
        <select
          className="mt-1 block w-full rounded border border-gray-300 p-2"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          {providers.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </label>
      <label className="block">
        <span className="block text-sm font-medium">Model</span>
        <input
          className="mt-1 block w-full rounded border border-gray-300 p-2"
          value={model}
          onChange={(e) => setModel(e.target.value)}
        />
      </label>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={saveAsDefault}
          onChange={(e) => setSaveAsDefault(e.target.checked)}
        />
        <span className="text-sm">Save as default</span>
      </label>
      <button
        type="submit"
        disabled={isPending}
        className="rounded bg-sage-600 px-4 py-2 text-white disabled:opacity-50"
      >
        {isPending ? "Applying…" : "Apply"}
      </button>
    </form>
  );
}
