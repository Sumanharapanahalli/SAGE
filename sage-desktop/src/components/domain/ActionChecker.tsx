import { useState } from "react";

import type { CheckActionResult, DesktopError } from "@/api/types";
import { useCheckAction } from "@/hooks/useConstitution";

function errorMessage(error: DesktopError): string {
  if (error.kind === "InvalidParams" || error.kind === "SidecarDown") {
    return `${error.kind}: ${error.detail.message}`;
  }
  return `Failed (${error.kind}).`;
}

export function ActionChecker() {
  const [desc, setDesc] = useState("");
  const check = useCheckAction();
  const result: CheckActionResult | undefined = check.data;

  return (
    <section className="space-y-2" data-testid="action-checker">
      <header>
        <h3 className="text-sm font-semibold">Action checker</h3>
        <p className="text-xs text-slate-500">
          Dry-run a description against the current constraints.
        </p>
      </header>
      <textarea
        aria-label="action description"
        className="block h-20 w-full rounded border border-slate-300 p-2 font-mono text-xs"
        value={desc}
        onChange={(e) => setDesc(e.target.value)}
        placeholder="Describe an action the agent might take…"
      />
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={!desc.trim() || check.isPending}
          className="rounded bg-sage-600 px-3 py-1 text-sm text-white hover:bg-sage-700 disabled:opacity-50"
          onClick={() => check.mutate(desc)}
        >
          {check.isPending ? "Checking…" : "Check"}
        </button>
        {check.error && (
          <span className="text-xs text-red-700" role="alert">
            {errorMessage(check.error)}
          </span>
        )}
      </div>
      {result && (
        <div
          role="status"
          className={
            result.allowed
              ? "rounded border border-green-200 bg-green-50 p-2 text-xs text-green-900"
              : "rounded border border-red-200 bg-red-50 p-2 text-xs text-red-900"
          }
        >
          <div className="font-semibold">
            {result.allowed ? "Allowed" : "Blocked"}
          </div>
          {!result.allowed && result.violations.length > 0 && (
            <ul className="mt-1 list-inside list-disc">
              {result.violations.map((v, i) => (
                <li key={i}>{v}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
