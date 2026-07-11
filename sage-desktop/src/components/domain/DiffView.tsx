/**
 * Unified-diff renderer for code_diff proposals.
 *
 * The desktop app rendered a proposal's payload as escaped JSON, which meant an
 * operator approving a code_diff could not actually READ the diff they were
 * approving — the one thing the HITL gate exists to let them do. A `\n`-laden
 * JSON blob is not a reviewable change.
 */

interface DiffViewProps {
  diff: string;
  summary?: string;
  writtenFiles?: string[];
  testsPassed?: boolean | null;
  testResult?: string;
}

function lineClass(line: string): string {
  // Order matters: the +++/--- file headers must be classed as headers, not as
  // additions/removals, or every diff opens with a misleading green/red pair.
  if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff ")) {
    return "text-slate-400";
  }
  if (line.startsWith("@@")) return "bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300";
  if (line.startsWith("+")) return "bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300";
  if (line.startsWith("-")) return "bg-rose-50 text-rose-800 dark:bg-rose-950 dark:text-rose-300";
  return "text-slate-600 dark:text-slate-400";
}

export function DiffView({
  diff,
  summary,
  writtenFiles,
  testsPassed,
  testResult,
}: DiffViewProps) {
  const lines = diff ? diff.split("\n") : [];

  return (
    <div className="mb-3 space-y-2">
      {summary && <p className="text-sm text-sage-900">{summary}</p>}

      {writtenFiles && writtenFiles.length > 0 && (
        <div className="text-xs text-slate-500">
          <span className="font-medium">Files changed:</span>{" "}
          {writtenFiles.map((f) => (
            <code key={f} className="mr-1 rounded bg-sage-50 px-1 py-0.5 font-mono">
              {f}
            </code>
          ))}
        </div>
      )}

      {testsPassed != null && (
        <div
          className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${
            testsPassed
              ? "bg-emerald-100 text-emerald-800"
              : "bg-rose-100 text-rose-800"
          }`}
          title={testResult}
        >
          {testsPassed ? "Tests passed" : "Tests FAILED"}
        </div>
      )}

      {lines.length > 0 ? (
        <pre className="max-h-96 overflow-auto rounded border border-sage-100 text-xs leading-relaxed">
          {lines.map((line, i) => (
            <div key={i} className={`px-3 font-mono ${lineClass(line)}`}>
              {line || " "}
            </div>
          ))}
        </pre>
      ) : (
        <p className="text-xs italic text-slate-400">
          No diff content in this proposal.
        </p>
      )}
    </div>
  );
}
