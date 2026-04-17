import { useState } from "react";

import { useInstallUpdate, useUpdateCheck } from "@/hooks/useUpdate";

export function UpdatePanel() {
  const [enabled, setEnabled] = useState(false);
  const check = useUpdateCheck(enabled);
  const install = useInstallUpdate();

  return (
    <div>
      <button
        type="button"
        className="rounded bg-gray-800 px-3 py-1.5 text-sm text-white disabled:opacity-50"
        onClick={() => {
          setEnabled(true);
          check.refetch();
        }}
        disabled={check.isFetching}
      >
        {check.isFetching ? "Checking…" : "Check for updates"}
      </button>

      {check.isError && (
        <p className="mt-2 text-sm text-red-700">
          Update check failed: {check.error.kind}
        </p>
      )}

      {check.data?.kind === "UpToDate" && (
        <p className="mt-2 text-sm text-green-700">
          You're on the latest version ({check.data.current_version}).
        </p>
      )}

      {check.data?.kind === "Error" && (
        <p className="mt-2 text-sm text-red-700">
          Updater error: {check.data.detail}
        </p>
      )}

      {check.data?.kind === "Available" && (
        <div className="mt-3 space-y-2">
          <p className="text-sm">
            New version <span className="font-mono">{check.data.new_version}</span>{" "}
            available (you have{" "}
            <span className="font-mono">{check.data.current_version}</span>).
          </p>
          {check.data.notes && (
            <pre className="max-h-40 overflow-auto whitespace-pre-wrap rounded bg-gray-50 p-2 text-xs text-gray-700">
              {check.data.notes}
            </pre>
          )}
          <button
            type="button"
            className="rounded bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            onClick={() => install.mutate()}
            disabled={install.isPending}
          >
            {install.isPending ? "Installing…" : "Download & restart"}
          </button>
          {install.isError && (
            <p className="text-sm text-red-700">
              Install failed: {install.error.kind}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
