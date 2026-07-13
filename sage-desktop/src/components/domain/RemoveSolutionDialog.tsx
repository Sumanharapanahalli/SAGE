import { useState } from "react";

import type { DesktopError, RemoveSolutionMode, SolutionRef } from "@/api/types";

interface Props {
  solution: SolutionRef;
  isPending: boolean;
  error: DesktopError | null;
  onCancel: () => void;
  onConfirm: (mode: RemoveSolutionMode, confirm?: string) => void;
}

/**
 * Confirmation panel for removing a solution.
 *
 * Two modes, and the safe one is the default:
 *  - **Archive** (default): the sidecar moves the directory into
 *    `<solutions_dir>/.archive/` — it disappears from the picker, nothing is
 *    destroyed, and a human can move it back.
 *  - **Delete**: really removes the directory from disk. The operator must
 *    type the solution name exactly; the sidecar independently re-checks that
 *    `confirm === name` and refuses anything outside the solutions dir.
 *
 * Fully controlled apart from the local mode/typed-name state: the parent owns
 * the mutation.
 */
export function RemoveSolutionDialog({
  solution,
  isPending,
  error,
  onCancel,
  onConfirm,
}: Props) {
  const [mode, setMode] = useState<RemoveSolutionMode>("archive");
  const [typed, setTyped] = useState("");

  const deleteBlocked = mode === "delete" && typed !== solution.name;

  return (
    <div
      className="mt-2 rounded border border-red-300 bg-red-50 p-3"
      data-testid="remove-solution-dialog"
      role="group"
      aria-label={`Remove ${solution.name}`}
    >
      <p className="text-sm font-medium text-red-900">
        Remove {solution.name}?
      </p>

      <label className="mt-2 flex items-start gap-2 text-sm">
        <input
          type="radio"
          name="remove-mode"
          value="archive"
          checked={mode === "archive"}
          onChange={() => setMode("archive")}
          className="mt-1"
        />
        <span>
          <span className="font-medium">Archive (recommended)</span>
          <span className="block text-xs text-slate-600">
            Moves the folder into <code>.archive/</code> and hides it from the
            picker. Nothing is deleted — you can move it back at any time.
          </span>
        </span>
      </label>

      <label className="mt-2 flex items-start gap-2 text-sm">
        <input
          type="radio"
          name="remove-mode"
          value="delete"
          checked={mode === "delete"}
          onChange={() => setMode("delete")}
          className="mt-1"
        />
        <span>
          <span className="font-medium text-red-800">
            Delete permanently from disk
          </span>
          <span className="block text-xs text-slate-600">
            Erases {solution.path} — including its YAML, tests, tools and all
            SAGE data. This cannot be undone.
          </span>
        </span>
      </label>

      {mode === "delete" && (
        <label className="mt-2 block text-sm">
          <span className="block text-xs text-slate-700">
            Type <code>{solution.name}</code> to confirm
          </span>
          <input
            type="text"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            aria-label="type the solution name to confirm deletion"
            className="mt-1 w-full rounded border border-red-300 px-2 py-1 text-sm"
          />
        </label>
      )}

      {error && (
        <p className="mt-2 text-sm text-red-700" role="alert">
          Remove failed ({error.kind}).
        </p>
      )}

      <div className="mt-3 flex gap-2">
        <button
          type="button"
          onClick={() =>
            onConfirm(mode, mode === "delete" ? typed : undefined)
          }
          disabled={isPending || deleteBlocked}
          className="rounded bg-red-700 px-3 py-1 text-sm text-white disabled:opacity-50"
        >
          {mode === "delete" ? "Delete permanently" : "Archive"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isPending}
          className="rounded border border-slate-300 px-3 py-1 text-sm disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
