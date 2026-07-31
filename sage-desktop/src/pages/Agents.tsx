import { useEffect, useState } from "react";

import { AgentCard } from "@/components/domain/AgentCard";
import { ErrorBanner } from "@/components/layout/ErrorBanner";
import {
  useAnalyzeJobDescription,
  useHireAgent,
  useProjectConfig,
  useRunAgent,
} from "@/hooks/useAgentRun";
import { useAgentPerformance, useAgents } from "@/hooks/useAgents";
import { normalizeTaskTypes } from "@/lib/taskTypes";

/**
 * Agents — the roster, plus the execution half.
 *
 * The roster was read-only: the operator could see which roles existed but
 * never use one. Run and Hire sit on the `agentrun.*` RPCs.
 *
 * Both mutating tabs end at a PROPOSAL, never at an effect. Running persists
 * the result for review (the web API's POST /agent/run returned
 * status:"pending_review" and stored nothing, so its banner was decorative),
 * and hiring never writes prompts.yaml here — that happens on approval, in
 * proposal_executor._execute_agent_hire. The copy has to say so: telling the
 * operator the role was created would be false until a human approves.
 */

const TABS = [
  { id: "roster", label: "Roster" },
  { id: "run", label: "Run" },
  { id: "hire", label: "Hire" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const inputCls =
  "mt-1 w-full rounded border border-sage-200 px-2 py-1 text-sm focus:border-sage-400 focus:outline-none";
const btnCls =
  "rounded bg-sage-500 px-4 py-2 text-sm font-medium text-white hover:bg-sage-600 disabled:opacity-50";

export function Agents() {
  const [tab, setTab] = useState<TabId>("roster");

  return (
    <div className="space-y-4">
      <div role="tablist" className="flex gap-1 border-b border-sage-100">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => setTab(t.id)}
            className={
              tab === t.id
                ? "border-b-2 border-sage-500 px-4 py-2 text-sm font-medium text-sage-900"
                : "px-4 py-2 text-sm text-sage-700 hover:text-sage-900"
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "roster" && <Roster />}
      {/* Mounted only while visible so the runnable-roster fetch does not fire
          on a tab that never shows it. */}
      {tab === "run" && <RunPanel />}
      {tab === "hire" && <HirePanel />}
    </div>
  );
}

// ── Roster ─────────────────────────────────────────────────────────────────

function Roster() {
  const { data, isLoading, error } = useAgents();
  const [selected, setSelected] = useState<string | null>(null);
  const performance = useAgentPerformance(selected ?? "", selected !== null);

  if (isLoading) return <p className="text-sm text-slate-500">Loading agents…</p>;
  if (error) return <ErrorBanner error={error} />;
  if (!data || data.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
        No agents configured for this solution.
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.map((a) => (
          <AgentCard
            key={a.name}
            agent={a}
            selected={selected === a.name}
            onSelect={setSelected}
          />
        ))}
      </div>
      {selected && (
        <div className="rounded-lg border border-sage-100 bg-white p-4 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-sage-900">
            Performance — {selected}
          </h3>
          {performance.isLoading && (
            <p className="text-sm text-slate-500">Loading performance…</p>
          )}
          {performance.error && <ErrorBanner error={performance.error} />}
          {performance.data && (
            <dl className="grid grid-cols-2 gap-3 text-xs text-slate-500 sm:grid-cols-4">
              <div>
                <dt className="font-medium text-slate-400">Total proposals</dt>
                <dd className="text-base text-sage-900">
                  {performance.data.total_proposals}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-400">Approved</dt>
                <dd className="text-base text-sage-900">
                  {performance.data.approved}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-400">Rejected</dt>
                <dd className="text-base text-sage-900">
                  {performance.data.rejected}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-slate-400">Approval rate</dt>
                <dd className="text-base text-sage-900">
                  {performance.data.approval_rate === null
                    ? "No history yet"
                    : `${performance.data.approval_rate}%`}
                </dd>
              </div>
            </dl>
          )}
        </div>
      )}
    </div>
  );
}

// ── Run ────────────────────────────────────────────────────────────────────

function RunPanel() {
  // Deliberately NOT useAgents(): that roster is audit-annotated and also
  // includes the four core roles, which UniversalAgent.run cannot dispatch to.
  // Offering one would be a guaranteed "unknown role" error.
  const project = useProjectConfig();
  const run = useRunAgent();

  const [roleId, setRoleId] = useState("");
  const [task, setTask] = useState("");
  const [context, setContext] = useState("");

  const roles = project.data?.agents ?? [];

  useEffect(() => {
    if (!roleId && roles.length > 0) setRoleId(roles[0].id);
  }, [roleId, roles]);

  return (
    <section className="space-y-4">
      {project.error && <ErrorBanner error={project.error} />}
      {run.error && <ErrorBanner error={run.error} />}

      {project.isLoading && (
        <p className="text-sm text-slate-500">Loading runnable roles…</p>
      )}
      {!project.isLoading && roles.length === 0 && (
        <div className="rounded border border-sage-100 bg-white p-6 text-center text-sm text-slate-500">
          This solution declares no runnable roles under <code>roles:</code> in
          prompts.yaml.
        </div>
      )}

      {roles.length > 0 && (
        <>
          <label className="block max-w-sm text-xs text-sage-700">
            Role
            <select
              className={inputCls}
              value={roleId}
              onChange={(e) => setRoleId(e.target.value)}
            >
              {roles.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs text-sage-700">
            Task
            <textarea
              className={inputCls}
              rows={3}
              value={task}
              onChange={(e) => setTask(e.target.value)}
            />
          </label>

          <label className="block text-xs text-sage-700">
            Context (optional)
            <textarea
              className={inputCls}
              rows={2}
              value={context}
              onChange={(e) => setContext(e.target.value)}
            />
          </label>

          <button
            className={btnCls}
            disabled={run.isPending || !roleId || !task.trim()}
            onClick={() => run.mutate({ role_id: roleId, task, context })}
          >
            {run.isPending ? "Running…" : "Run agent"}
          </button>
        </>
      )}

      {run.data && (
        <div className="space-y-3">
          <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            <div className="font-semibold">Awaiting human approval</div>
            <div className="mt-1 text-xs">
              The run was saved as a proposal — {run.data.proposal.description}.
              Decide on it in the Approvals inbox.
            </div>
          </div>
          <div>
            <div className="text-xs uppercase text-sage-700">Agent result</div>
            <pre className="mt-1 overflow-x-auto rounded bg-sage-50 p-3 text-xs">
              {JSON.stringify(run.data.result, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </section>
  );
}

// ── Hire ───────────────────────────────────────────────────────────────────

function HirePanel() {
  const analyze = useAnalyzeJobDescription();
  const hire = useHireAgent();

  const [jd, setJd] = useState("");
  const [roleId, setRoleId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [taskTypes, setTaskTypes] = useState("");

  const runAnalyze = () => {
    analyze.mutate(
      { jd_text: jd },
      {
        onSuccess: (draft) => {
          // agent_factory returns `role_key`; the hire payload wants
          // `role_id`. And task_types arrive as {name, description} objects
          // while hire validates plain strings — normalizeTaskTypes bridges
          // both shapes, since nothing enforces the LLM's output.
          if (draft.role_key) setRoleId(draft.role_key);
          setName(draft.name ?? "");
          setDescription(draft.description ?? "");
          setSystemPrompt(draft.system_prompt ?? "");
          setTaskTypes(normalizeTaskTypes(draft.task_types).join(", "));
        },
      },
    );
  };

  const canHire =
    roleId.trim() !== "" && name.trim() !== "" && systemPrompt.trim() !== "";

  return (
    <section className="space-y-4">
      {analyze.error && <ErrorBanner error={analyze.error} />}
      {hire.error && <ErrorBanner error={hire.error} />}

      <label className="block text-xs text-sage-700">
        Job description
        <textarea
          className={inputCls}
          rows={4}
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          placeholder="Paste a job description and let the LLM draft the role."
        />
      </label>
      <button
        className="rounded border border-sage-200 px-3 py-2 text-sm text-sage-700 hover:bg-sage-50 disabled:opacity-50"
        disabled={analyze.isPending || !jd.trim()}
        onClick={runAnalyze}
      >
        {analyze.isPending ? "Analyzing…" : "Analyze job description"}
      </button>

      <div className="grid gap-3 md:grid-cols-2">
        <label className="block text-xs text-sage-700">
          Role ID
          <input
            className={inputCls}
            value={roleId}
            onChange={(e) => setRoleId(e.target.value)}
            placeholder="lowercase_snake_case"
          />
        </label>
        <label className="block text-xs text-sage-700">
          Name
          <input
            className={inputCls}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
      </div>

      <label className="block text-xs text-sage-700">
        Description
        <input
          className={inputCls}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>

      <label className="block text-xs text-sage-700">
        System prompt
        <textarea
          className={inputCls}
          rows={4}
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
        />
      </label>

      <label className="block text-xs text-sage-700">
        Task types (comma separated)
        <input
          className={inputCls}
          value={taskTypes}
          onChange={(e) => setTaskTypes(e.target.value)}
        />
      </label>

      <button
        className={btnCls}
        disabled={hire.isPending || !canHire}
        onClick={() =>
          hire.mutate({
            role_id: roleId.trim(),
            name: name.trim(),
            system_prompt: systemPrompt,
            description,
            task_types: normalizeTaskTypes(
              taskTypes.split(",").map((t) => t.trim()),
            ),
          })
        }
      >
        {hire.isPending ? "Proposing…" : "Propose hire"}
      </button>

      {hire.data && (
        <div className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <div className="font-semibold">Awaiting human approval</div>
          <div className="mt-1 text-xs">
            {hire.data.description}. Nothing has been written to prompts.yaml —
            the role becomes available only once the proposal is approved.
          </div>
        </div>
      )}
    </section>
  );
}
