import { useState } from "react";

import type { DesktopError } from "@/api/types";
import { CollectiveStats } from "@/components/domain/CollectiveStats";
import { CreateHelpRequestForm } from "@/components/domain/CreateHelpRequestForm";
import { HelpRequestCard } from "@/components/domain/HelpRequestCard";
import { LearningRow } from "@/components/domain/LearningRow";
import { PublishLearningForm } from "@/components/domain/PublishLearningForm";
import {
  useClaimHelpRequest,
  useCloseHelpRequest,
  useCollectiveHelpList,
  useCollectiveList,
  useCollectiveStats,
  useCollectiveSync,
  useCreateHelpRequest,
  usePublishLearning,
  useRespondToHelpRequest,
  useValidateLearning,
} from "@/hooks/useCollective";

type Tab = "learnings" | "help" | "stats";

function errorMessage(e: DesktopError): string {
  if (
    e.kind === "InvalidParams" ||
    e.kind === "SidecarDown" ||
    e.kind === "SolutionUnavailable"
  ) {
    return `${e.kind}: ${e.detail.message}`;
  }
  if (e.kind === "Other") return e.detail.message;
  return `Failed (${e.kind}).`;
}

export default function Collective() {
  const [tab, setTab] = useState<Tab>("learnings");
  const [helpStatus, setHelpStatus] = useState<"open" | "closed">("open");
  const [publishNotice, setPublishNotice] = useState<string | null>(null);

  const stats = useCollectiveStats();
  const learnings = useCollectiveList({ limit: 50, offset: 0 });
  const help = useCollectiveHelpList({ status: helpStatus });
  const publish = usePublishLearning();
  const validate = useValidateLearning();
  const createHelp = useCreateHelpRequest();
  const claim = useClaimHelpRequest();
  const respond = useRespondToHelpRequest();
  const close = useCloseHelpRequest();
  const sync = useCollectiveSync();

  const gitAvailable = stats.data?.git_available ?? false;

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <header className="space-y-1">
        <div className="flex items-baseline justify-between">
          <div>
            <h2 className="text-lg font-semibold">Collective Intelligence</h2>
            <p className="text-sm text-slate-600">
              Git-backed knowledge sharing across every solution on this host.
            </p>
          </div>
          <button
            type="button"
            onClick={() => sync.mutate()}
            disabled={!gitAvailable || sync.isPending}
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
          >
            {sync.isPending ? "syncing…" : "Sync"}
          </button>
        </div>
        {stats.data && (
          <div className="flex flex-wrap gap-3 text-xs text-slate-500">
            <span className="font-mono">{stats.data.repo_path}</span>
            <span
              className={
                gitAvailable ? "text-emerald-700" : "text-amber-700"
              }
            >
              {gitAvailable
                ? "git: available"
                : "git: offline (local-only commits suppressed)"}
            </span>
            <span>
              {stats.data.learning_count} learnings ·{" "}
              {stats.data.help_request_count} open help ·{" "}
              {stats.data.help_requests_closed} closed
            </span>
          </div>
        )}
        {stats.isError && (
          <div className="rounded border border-rose-300 bg-rose-50 p-2 text-sm text-rose-700">
            {errorMessage(stats.error as DesktopError)}
          </div>
        )}
      </header>

      <nav className="flex gap-2 border-b border-slate-200">
        {(["learnings", "help", "stats"] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`px-3 py-1 text-sm ${
              tab === t
                ? "border-b-2 border-sky-600 font-semibold text-slate-900"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {t === "help" ? "Help Requests" : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      {tab === "learnings" && (
        <section className="space-y-3">
          {learnings.isLoading && (
            <div className="text-sm text-slate-500">Loading…</div>
          )}
          {learnings.isError && (
            <div className="rounded border border-rose-300 bg-rose-50 p-2 text-sm text-rose-700">
              {errorMessage(learnings.error as DesktopError)}
            </div>
          )}
          {learnings.data?.entries.map((l) => (
            <LearningRow
              key={l.id}
              learning={l}
              onValidate={(id) =>
                validate.mutate({ id, validated_by: "operator@desktop" })
              }
              isValidating={validate.isPending}
            />
          ))}
          {publishNotice && (
            <div className="rounded border border-emerald-300 bg-emerald-50 p-2 text-sm text-emerald-800">
              {publishNotice}
            </div>
          )}
          <PublishLearningForm
            isSubmitting={publish.isPending}
            onSubmit={(payload) => {
              publish.mutate(
                { ...payload, proposed_by: "operator@desktop" },
                {
                  onSuccess: (res) => {
                    setPublishNotice(
                      res.gated
                        ? `Submitted as proposal ${res.trace_id}`
                        : `Published id=${res.id}`,
                    );
                  },
                },
              );
            }}
          />
        </section>
      )}

      {tab === "help" && (
        <section className="space-y-3">
          <div className="flex gap-2">
            {(["open", "closed"] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setHelpStatus(s)}
                className={`rounded px-2 py-1 text-xs ${
                  helpStatus === s
                    ? "bg-slate-800 text-white"
                    : "border border-slate-300 bg-white text-slate-700"
                }`}
              >
                {s[0].toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
          {help.data?.entries.map((r) => (
            <HelpRequestCard
              key={r.id}
              request={r}
              onClaim={(id) =>
                claim.mutate({
                  id,
                  agent: "operator",
                  solution: "desktop",
                })
              }
              onRespond={(id) => {
                const content = window.prompt("Response:");
                if (content && content.trim()) {
                  respond.mutate({
                    id,
                    responder_agent: "operator",
                    responder_solution: "desktop",
                    content: content.trim(),
                  });
                }
              }}
              onClose={(id) => close.mutate(id)}
            />
          ))}
          <CreateHelpRequestForm
            isSubmitting={createHelp.isPending}
            onSubmit={(payload) => createHelp.mutate(payload)}
          />
        </section>
      )}

      {tab === "stats" && stats.data && <CollectiveStats stats={stats.data} />}
    </div>
  );
}
