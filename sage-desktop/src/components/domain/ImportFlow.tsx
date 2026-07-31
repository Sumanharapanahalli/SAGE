import { useState } from "react";

import type { SolutionDraftFiles } from "@/api/types";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import { useSaveSolution, useScanFolder } from "@/hooks/useOnboarding";

/**
 * Import an EXISTING codebase as a solution.
 *
 * Two deliberately separate steps. `scan_folder` reads the folder, asks the
 * LLM to draft project/prompts/tasks.yaml, and writes NOTHING; `save_solution`
 * is the write. So the operator always sees the drafts before anything lands
 * on disk — the same split the web onboarding flow uses, minus its bug (see
 * below).
 *
 * The web endpoints behind this (api.py:4081 scan-folder, api.py:4125 refine)
 * call `llm.generate(system_prompt=..., user_prompt=...)`, but
 * `LLMGateway.generate` takes `prompt` and has no `**kwargs` — so they raise
 * TypeError on every call and report it as 503 "Could not reach the LLM". The
 * sidecar handler calls `prompt=`, and a test pins it.
 */

interface Props {
  /** Called once the solution is on disk. Both values are needed to switch
   *  into it — `useSwitchSolution` takes {name, path}. */
  onSaved?: (solutionName: string, path: string) => void;
}

const inputCls =
  "mt-1 w-full rounded border border-sage-200 px-2 py-1 text-sm focus:border-sage-400 focus:outline-none";

export function ImportFlow({ onSaved }: Props) {
  const scan = useScanFolder();
  const save = useSaveSolution();

  const [folderPath, setFolderPath] = useState("");
  const [solutionName, setSolutionName] = useState("");
  const [intent, setIntent] = useState("");

  const drafts: SolutionDraftFiles | null = scan.data?.files ?? null;
  const summary = scan.data?.summary;

  return (
    <div className="space-y-4">
      <p className="text-sm text-sage-700">
        Point SAGE at an existing codebase. It reads the folder and drafts the
        YAML triad — nothing is written until you save.
      </p>

      <ErrorBanner error={scan.error} />
      <ErrorBanner error={save.error} />

      <label className="block text-xs text-sage-700">
        Folder path
        <input
          className={inputCls}
          value={folderPath}
          onChange={(e) => setFolderPath(e.target.value)}
          placeholder="/path/to/your/project"
        />
      </label>

      <label className="block text-xs text-sage-700">
        Solution name
        <input
          className={inputCls}
          value={solutionName}
          onChange={(e) => setSolutionName(e.target.value)}
          placeholder="letters, digits, _ or -"
        />
      </label>

      <label className="block text-xs text-sage-700">
        Intent (optional)
        <textarea
          className={inputCls}
          rows={2}
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          placeholder="What should SAGE help you do with this codebase?"
        />
      </label>

      <button
        className="rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
        disabled={
          scan.isPending || !folderPath.trim() || !solutionName.trim()
        }
        onClick={() =>
          scan.mutate({
            folder_path: folderPath,
            solution_name: solutionName,
            intent,
          })
        }
      >
        {scan.isPending ? "Scanning…" : "Scan folder"}
      </button>

      {drafts && (
        <div className="space-y-3 rounded border border-sage-100 p-4">
          <div className="text-sm font-semibold text-sage-900">
            Drafted from the codebase — review before saving
          </div>

          {summary && (
            <dl className="grid gap-2 text-xs text-sage-700 sm:grid-cols-2">
              <div>
                <dt className="text-slate-400">Name</dt>
                <dd className="text-sage-900">{summary.name || "—"}</dd>
              </div>
              <div>
                <dt className="text-slate-400">Description</dt>
                <dd className="text-sage-900">{summary.description || "—"}</dd>
              </div>
              {summary.task_types.length > 0 && (
                <div className="sm:col-span-2">
                  <dt className="text-slate-400">Task types</dt>
                  <dd className="text-sage-900">
                    {summary.task_types.map((t) => t.name).join(", ")}
                  </dd>
                </div>
              )}
            </dl>
          )}

          {Object.entries(drafts).map(([filename, content]) => (
            <details key={filename} className="rounded bg-sage-50 p-2">
              <summary className="cursor-pointer text-xs font-medium text-sage-900">
                {filename}
              </summary>
              <pre className="mt-2 overflow-x-auto text-xs">{content}</pre>
            </details>
          ))}

          <button
            className="rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
            disabled={save.isPending}
            onClick={() =>
              save.mutate(
                { solution_name: scan.data!.solution_name, files: drafts },
                { onSuccess: (r) => onSaved?.(r.solution_name, r.path) },
              )
            }
          >
            {save.isPending ? "Saving…" : "Save solution"}
          </button>
        </div>
      )}

      {save.data && (
        <div className="rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">
          <div className="font-semibold">Solution saved</div>
          <div className="mt-1 text-xs">
            Wrote {save.data.files_written.join(", ")} to{" "}
            <span className="font-mono">{save.data.path}</span>.
          </div>
        </div>
      )}
    </div>
  );
}
