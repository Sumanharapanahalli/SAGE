import type { CurrentSolution, DesktopError, SolutionRef } from "@/api/types";

interface Props {
  solutions: SolutionRef[];
  current: CurrentSolution | null | undefined;
  isLoading: boolean;
  isSwitching: boolean;
  switchError: DesktopError | null;
  onSwitch: (s: SolutionRef) => void;
}

/**
 * Dropdown + apply button for choosing which solution the sidecar is
 * attached to.
 *
 * The component is fully controlled: selection is stored in the native
 * `<select>` via `value`, and the caller decides what to do on apply.
 * It also has no local state — parents pass the current selection in,
 * we only emit events.
 */
export function SolutionPicker({
  solutions,
  current,
  isLoading,
  isSwitching,
  switchError,
  onSwitch,
}: Props) {
  const selectedName = current?.name ?? "";

  const handleChange = (name: string) => {
    const match = solutions.find((s) => s.name === name);
    if (match && match.name !== current?.name) {
      onSwitch(match);
    }
  };

  if (isLoading) {
    return (
      <div className="text-sm text-gray-500">Loading solutions…</div>
    );
  }

  if (solutions.length === 0) {
    return (
      <div className="text-sm text-gray-500">
        No solutions found. Create one under <code>solutions/</code>.
      </div>
    );
  }

  return (
    <div className="space-y-2" data-testid="solution-picker">
      <label className="block">
        <span className="block text-sm font-medium">Active solution</span>
        <select
          className="mt-1 block w-full rounded border border-gray-300 p-2 disabled:opacity-50"
          value={selectedName}
          disabled={isSwitching}
          onChange={(e) => handleChange(e.target.value)}
          aria-label="Active solution"
        >
          {selectedName === "" && <option value="">— none —</option>}
          {solutions.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name}
              {s.has_sage_dir ? "" : " (new)"}
            </option>
          ))}
        </select>
      </label>
      {isSwitching && (
        <div className="text-sm text-gray-500" role="status">
          Switching sidecar…
        </div>
      )}
      {switchError && (
        <div className="text-sm text-red-700" role="alert">
          {switchError.kind === "SolutionNotFound"
            ? `Solution not found: ${switchError.detail.name}`
            : `Switch failed (${switchError.kind}).`}
        </div>
      )}
    </div>
  );
}
