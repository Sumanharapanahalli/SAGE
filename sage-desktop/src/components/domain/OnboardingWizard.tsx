import { useState } from "react";

import type {
  DesktopError,
  OnboardingParams,
  OnboardingResult,
} from "@/api/types";

const NAME_RE = /^[a-z][a-z0-9_]*$/;
const MIN_DESC = 30;

interface Props {
  isPending: boolean;
  error: DesktopError | null;
  result: OnboardingResult | null;
  onGenerate: (p: OnboardingParams) => void;
  onSwitch: (name: string, path: string) => void;
  onClose: () => void;
}

function splitCsv(value: string): string[] {
  return value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function errorMessage(error: DesktopError): string {
  if (error.kind === "InvalidParams" || error.kind === "SidecarDown") {
    return `${error.kind}: ${error.detail.message}`;
  }
  return `Generation failed (${error.kind}).`;
}

export function OnboardingWizard({
  isPending,
  error,
  result,
  onGenerate,
  onSwitch,
  onClose,
}: Props) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [standards, setStandards] = useState("");
  const [integrations, setIntegrations] = useState("");

  const trimmedName = name.trim();
  const trimmedDesc = desc.trim();
  const nameOk = NAME_RE.test(trimmedName);
  const descOk = trimmedDesc.length >= MIN_DESC;
  const canSubmit = nameOk && descOk && !isPending;

  if (result) {
    return (
      <div className="space-y-3" data-testid="onboarding-result">
        {result.status === "created" ? (
          <>
            <div className="rounded border border-green-200 bg-green-50 p-4 text-sm">
              <div className="font-semibold">
                Created '{result.solution_name}'
              </div>
              <div className="mt-1 font-mono">{result.path}</div>
              <div className="mt-1 text-xs text-green-800/80">
                {Object.keys(result.files).join(", ")}
              </div>
              {result.suggested_routes.length > 0 && (
                <div className="mt-2 text-xs">
                  Suggested routes: {result.suggested_routes.join(", ")}
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded bg-sage-600 px-4 py-2 text-white hover:bg-sage-700"
                onClick={() =>
                  onSwitch(result.solution_name, result.path)
                }
              >
                Switch to it
              </button>
              <button
                type="button"
                className="rounded border border-gray-300 px-4 py-2"
                onClick={onClose}
              >
                Stay on current
              </button>
            </div>
          </>
        ) : (
          <div className="rounded border border-yellow-200 bg-yellow-50 p-4 text-sm">
            <div className="font-semibold">Already exists</div>
            <div className="mt-1">{result.message}</div>
            <button
              type="button"
              className="mt-3 rounded border border-gray-300 px-4 py-2"
              onClick={onClose}
            >
              OK
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        onGenerate({
          description: trimmedDesc,
          solution_name: trimmedName,
          compliance_standards: splitCsv(standards),
          integrations: splitCsv(integrations),
        });
      }}
    >
      <label className="block">
        <span className="block text-sm font-medium">Solution name</span>
        <input
          className="mt-1 block w-full rounded border border-gray-300 p-2 font-mono"
          placeholder="e.g. yoga"
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-invalid={Boolean(name) && !nameOk}
        />
        {name && !nameOk && (
          <span className="text-xs text-red-700">
            Must be snake_case (lowercase, digits, underscores).
          </span>
        )}
      </label>
      <label className="block">
        <span className="block text-sm font-medium">Description</span>
        <textarea
          className="mt-1 block w-full rounded border border-gray-300 p-2"
          rows={4}
          placeholder="A short description of the domain and what the solution should do."
          value={desc}
          onChange={(e) => setDesc(e.target.value)}
        />
        <span className="text-xs text-gray-500">
          {trimmedDesc.length}/{MIN_DESC} chars minimum
        </span>
      </label>
      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="block text-sm font-medium">
            Compliance (comma-separated)
          </span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            placeholder="ISO 9001, IEC 62304"
            value={standards}
            onChange={(e) => setStandards(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="block text-sm font-medium">Integrations</span>
          <input
            className="mt-1 block w-full rounded border border-gray-300 p-2"
            placeholder="gitlab, slack"
            value={integrations}
            onChange={(e) => setIntegrations(e.target.value)}
          />
        </label>
      </div>
      {error && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          {errorMessage(error)}
        </div>
      )}
      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded bg-sage-600 px-4 py-2 text-white hover:bg-sage-700 disabled:opacity-50"
      >
        {isPending ? "Asking LLM…" : "Generate"}
      </button>
    </form>
  );
}
