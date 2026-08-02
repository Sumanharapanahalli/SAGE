import { useEffect, useState } from "react";

import type { SolutionDraftFiles, SolutionDraftSummary } from "@/api/types";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useRefineSolution } from "@/hooks/useOnboarding";

/**
 * Review the drafted YAML triad before anything is written, with a
 * conversational refine loop.
 *
 * The loop is the point: refine returns the same shape it takes, so each pass
 * feeds the NEXT one. Accepting hands back whatever the drafts currently are,
 * refinements included — the caller owns the write.
 *
 * The web equivalent (`components/onboarding/ReviewPanel.tsx`) calls
 * `/onboarding/refine`, which has never worked: api.py:4125 passes
 * `user_prompt=` to `LLMGateway.generate`, which takes `prompt` and has no
 * `**kwargs`, so every call raises TypeError and is reported as 503
 * "Could not reach the LLM". The sidecar handler behind this calls `prompt=`.
 */

interface Props {
  solutionName: string;
  files: SolutionDraftFiles;
  summary?: SolutionDraftSummary;
  onAccept: (files: SolutionDraftFiles) => void;
  acceptLabel: string;
  isAccepting: boolean;
  /** Omit to hide the Start-over button — not every caller can discard. */
  onStartOver?: () => void;
}

const inputCls =
  "mt-1 w-full rounded border border-sage-200 px-2 py-1 text-sm focus:border-sage-400 focus:outline-none";

export function ReviewPanel({
  solutionName,
  files,
  summary,
  onAccept,
  acceptLabel,
  isAccepting,
  onStartOver,
}: Props) {
  const refine = useRefineSolution();

  const [draftFiles, setDraftFiles] = useState<SolutionDraftFiles>(files);
  const [draftSummary, setDraftSummary] = useState(summary);
  const [feedback, setFeedback] = useState("");

  // A fresh scan/generate replaces the drafts under us.
  useEffect(() => {
    setDraftFiles(files);
    setDraftSummary(summary);
  }, [files, summary]);

  const runRefine = () => {
    refine.mutate(
      {
        solution_name: solutionName,
        current_files: draftFiles,
        feedback,
      },
      {
        onSuccess: (result) => {
          setDraftFiles(result.files);
          setDraftSummary(result.summary);
          // Clear on success only: keeping it would invite re-sending the same
          // feedback against already-revised drafts. On failure it is kept, so
          // the operator does not have to retype it.
          setFeedback("");
        },
      },
    );
  };

  return (
    <div className="space-y-3 rounded border border-sage-100 p-4">
      <div className="text-sm font-semibold text-sage-900">
        Review before saving
      </div>

      <ErrorBanner error={refine.error} />

      {draftSummary && (
        <dl className="grid gap-2 text-xs text-sage-700 sm:grid-cols-2">
          <div>
            <dt className="text-slate-400">Name</dt>
            <dd className="text-sage-900">{draftSummary.name || "—"}</dd>
          </div>
          <div>
            <dt className="text-slate-400">Description</dt>
            <dd className="text-sage-900">{draftSummary.description || "—"}</dd>
          </div>
          {draftSummary.task_types.length > 0 && (
            <div className="sm:col-span-2">
              <dt className="text-slate-400">Task types</dt>
              <dd className="text-sage-900">
                {draftSummary.task_types.map((t) => t.name).join(", ")}
              </dd>
            </div>
          )}
        </dl>
      )}

      {/* Editable, not a preview: the LLM's YAML is a draft, and the operator
          is the last line of defence before it becomes a real solution. The
          sidecar validates every file parses before writing any of them. */}
      {Object.entries(draftFiles).map(([filename, content]) => (
        <details key={filename} className="rounded bg-sage-50 p-2">
          <summary className="cursor-pointer text-xs font-medium text-sage-900">
            {filename}
          </summary>
          {/* aria-label rather than a visible <label>: the <summary> already
              shows the filename, and a second node with the same text makes
              getByText ambiguous for no user-facing gain. */}
          <textarea
            aria-label={filename}
            className="mt-2 w-full rounded border border-sage-200 bg-white p-2 font-mono text-xs"
            rows={10}
            spellCheck={false}
            value={content}
            onChange={(e) =>
              setDraftFiles((prev) => ({ ...prev, [filename]: e.target.value }))
            }
          />
        </details>
      ))}

      <label className="block text-xs text-sage-700">
        Feedback — what should change?
        <textarea
          className={inputCls}
          rows={2}
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="e.g. add a task type for firmware review"
        />
      </label>

      <div className="flex gap-2">
        <button
          className="rounded border border-sage-200 px-3 py-2 text-sm text-sage-700 hover:bg-sage-50 disabled:opacity-50"
          disabled={refine.isPending || !feedback.trim()}
          onClick={runRefine}
        >
          {refine.isPending ? "Refining…" : "Refine"}
        </button>
        <button
          className="rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
          disabled={isAccepting || refine.isPending}
          onClick={() => onAccept(draftFiles)}
        >
          {isAccepting ? "Saving…" : acceptLabel}
        </button>
        {onStartOver && (
          <button
            className="ml-auto rounded px-3 py-2 text-sm text-sage-700 hover:bg-sage-50"
            disabled={isAccepting || refine.isPending}
            onClick={onStartOver}
          >
            Start over
          </button>
        )}
      </div>
    </div>
  );
}
