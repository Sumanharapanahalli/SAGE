import { useEffect, useMemo, useState } from "react";

import type {
  ConstitutionData,
  ConstitutionDecisions,
  ConstitutionPrinciple,
  ConstitutionVoice,
  DesktopError,
} from "@/api/types";
import { ActionChecker } from "@/components/domain/ActionChecker";
import { ConstraintsEditor } from "@/components/domain/ConstraintsEditor";
import { DecisionsEditor } from "@/components/domain/DecisionsEditor";
import { PreamblePreview } from "@/components/domain/PreamblePreview";
import { PrinciplesEditor } from "@/components/domain/PrinciplesEditor";
import { VersionHistoryList } from "@/components/domain/VersionHistoryList";
import { VoiceEditor } from "@/components/domain/VoiceEditor";
import {
  useConstitution,
  useUpdateConstitution,
} from "@/hooks/useConstitution";

function errorMessage(error: DesktopError): string {
  if (error.kind === "InvalidParams" || error.kind === "SidecarDown") {
    return `${error.kind}: ${error.detail.message}`;
  }
  return `Failed (${error.kind}).`;
}

function cloneData(data: ConstitutionData): ConstitutionData {
  return JSON.parse(JSON.stringify(data)) as ConstitutionData;
}

export default function Constitution() {
  const query = useConstitution();
  const update = useUpdateConstitution();
  const [draft, setDraft] = useState<ConstitutionData | null>(null);

  const loaded = query.data?.data;
  useEffect(() => {
    if (loaded) setDraft(cloneData(loaded));
  }, [loaded]);

  const dirty = useMemo(() => {
    if (!loaded || !draft) return false;
    return JSON.stringify(draft) !== JSON.stringify(loaded);
  }, [loaded, draft]);

  if (query.isLoading || !draft) {
    return (
      <div className="p-6 text-sm text-slate-600">Loading constitution…</div>
    );
  }

  if (query.isError) {
    return (
      <div
        role="alert"
        className="m-6 rounded border border-red-200 bg-red-50 p-4 text-sm text-red-900"
      >
        Could not load constitution: {errorMessage(query.error!)}
      </div>
    );
  }

  const setPrinciples = (principles: ConstitutionPrinciple[]) =>
    setDraft({ ...draft, principles });
  const setConstraints = (constraints: string[]) =>
    setDraft({ ...draft, constraints });
  const setVoice = (voice: ConstitutionVoice) =>
    setDraft({ ...draft, voice });
  const setDecisions = (decisions: ConstitutionDecisions) =>
    setDraft({ ...draft, decisions });

  const stats = query.data?.stats;
  const preamble = query.data?.preamble ?? "";
  const errors = query.data?.errors ?? [];
  const history = query.data?.history ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <header className="flex items-baseline justify-between">
        <div>
          <h2 className="text-lg font-semibold">Constitution</h2>
          <p className="text-sm text-slate-600">
            The operator-owned blue book. Prepended to every agent prompt.
          </p>
        </div>
        {stats && (
          <div className="text-right text-xs text-slate-500">
            <div className="font-semibold text-slate-700">{stats.name}</div>
            <div>v{stats.version}</div>
            <div>
              {stats.principle_count} principles · {stats.constraint_count}{" "}
              constraints · {stats.non_negotiable_count} non-negotiable
            </div>
          </div>
        )}
      </header>

      {errors.length > 0 && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          <div className="font-semibold">Validation errors on disk:</div>
          <ul className="mt-1 list-inside list-disc">
            {errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {update.error && (
        <div
          role="alert"
          className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
        >
          Save failed: {errorMessage(update.error)}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="space-y-6">
          <PrinciplesEditor
            principles={draft.principles ?? []}
            onChange={setPrinciples}
          />
          <ConstraintsEditor
            constraints={draft.constraints ?? []}
            onChange={setConstraints}
          />
          <VoiceEditor voice={draft.voice} onChange={setVoice} />
          <DecisionsEditor
            decisions={draft.decisions}
            onChange={setDecisions}
          />

          <div className="flex gap-2 pt-2">
            <button
              type="button"
              disabled={!dirty || update.isPending}
              className="rounded bg-sage-600 px-4 py-2 text-sm text-white hover:bg-sage-700 disabled:opacity-50"
              onClick={() => update.mutate({ data: draft })}
            >
              {update.isPending ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              disabled={!dirty}
              className="rounded border border-slate-300 px-4 py-2 text-sm disabled:opacity-50"
              onClick={() => loaded && setDraft(cloneData(loaded))}
            >
              Revert
            </button>
          </div>
        </div>

        <aside className="space-y-6">
          <PreamblePreview preamble={preamble} />
          <ActionChecker />
          <VersionHistoryList history={history} />
        </aside>
      </div>
    </div>
  );
}
