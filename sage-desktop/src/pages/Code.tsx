import { useState } from "react";

import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useCodeApprove,
  useCodeExecute,
  useCodePlan,
  useSandboxStatus,
} from "@/hooks/useCode";

/**
 * Sandboxed code execution: plan → approve → execute.
 *
 * The approval gate is enforced by `autogen_runner` itself, so Execute stays
 * disabled until approval lands AND the runner would refuse it anyway.
 *
 * The isolation warning is shown BEFORE the approve button rather than in the
 * result: when Docker is unavailable the runner falls back to a local
 * subprocess on this machine with no isolation, and the web UI only reveals
 * that after the code has already run.
 */
export default function Code() {
  const sandbox = useSandboxStatus();
  const planM = useCodePlan();
  const approveM = useCodeApprove();
  const executeM = useCodeExecute();

  const [task, setTask] = useState("");

  const runId = planM.data?.run_id;
  const approved = approveM.data?.status === "approved";
  const output = executeM.data?.output;

  return (
    <div className="space-y-4 p-6">
      <p className="text-sm text-sage-700">
        Describe a task; SAGE drafts a script. Nothing runs until you approve
        it.
      </p>

      {sandbox.data && !sandbox.data.isolated && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
        >
          <div className="font-semibold">No sandbox isolation</div>
          <div className="mt-1 text-xs">{sandbox.data.warning}</div>
        </div>
      )}
      {sandbox.data?.isolated && (
        <div className="text-xs text-sage-700">
          Sandbox: Docker, no network.
        </div>
      )}

      <ErrorBanner error={planM.error} />
      <ErrorBanner error={approveM.error} />
      <ErrorBanner error={executeM.error} />

      <label className="block text-xs text-sage-700">
        Task
        <textarea
          className="mt-1 w-full rounded border border-sage-200 px-2 py-1 text-sm focus:border-sage-400 focus:outline-none"
          rows={3}
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="e.g. parse this CSV and report the row count"
        />
      </label>
      <button
        className="rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
        disabled={planM.isPending || !task.trim()}
        onClick={() => planM.mutate(task)}
      >
        {planM.isPending ? "Planning…" : "Plan"}
      </button>

      {planM.data && (
        <div className="space-y-3 rounded border border-sage-100 p-4">
          <div className="text-xs uppercase text-sage-700">Plan</div>
          <pre className="overflow-x-auto rounded bg-sage-50 p-3 text-xs">
            {planM.data.plan}
          </pre>

          <div className="text-xs uppercase text-sage-700">Code to run</div>
          <pre className="overflow-x-auto rounded bg-sage-50 p-3 font-mono text-xs">
            {planM.data.code}
          </pre>

          <div className="flex gap-2">
            <button
              className="rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50"
              disabled={approveM.isPending || approved || !runId}
              onClick={() => approveM.mutate({ run_id: runId as string })}
            >
              {approved ? "Approved" : "Approve"}
            </button>
            <button
              className="rounded border border-sage-200 px-4 py-2 text-sm text-sage-700 hover:bg-sage-50 disabled:opacity-50"
              disabled={!approved || executeM.isPending}
              onClick={() => executeM.mutate(runId as string)}
            >
              {executeM.isPending ? "Running…" : "Execute"}
            </button>
          </div>
        </div>
      )}

      {output && (
        <div className="space-y-2 rounded border border-sage-100 p-4">
          <div className="text-xs uppercase text-sage-700">
            Output (exit {output.returncode ?? "?"} · {output.sandbox})
          </div>
          {output.warning && (
            <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              {output.warning}
            </div>
          )}
          {output.stdout && (
            <pre className="overflow-x-auto rounded bg-sage-50 p-3 text-xs">
              {output.stdout}
            </pre>
          )}
          {output.stderr && (
            <pre className="overflow-x-auto rounded bg-red-50 p-3 text-xs text-red-900">
              {output.stderr}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
