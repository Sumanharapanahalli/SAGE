import { useState } from "react";

import type { HelpRequestUrgency } from "@/api/types";

interface Payload {
  title: string;
  requester_agent: string;
  requester_solution: string;
  urgency: HelpRequestUrgency;
  required_expertise: string[];
  context: string;
}

interface Props {
  onSubmit: (payload: Payload) => void;
  isSubmitting?: boolean;
}

const URGENCIES: HelpRequestUrgency[] = ["low", "medium", "high", "critical"];

function parseList(raw: string): string[] {
  return raw
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
}

export function CreateHelpRequestForm({ onSubmit, isSubmitting }: Props) {
  const [title, setTitle] = useState("");
  const [requesterAgent, setRequesterAgent] = useState("");
  const [requesterSolution, setRequesterSolution] = useState("");
  const [urgency, setUrgency] = useState<HelpRequestUrgency>("medium");
  const [expertiseRaw, setExpertiseRaw] = useState("");
  const [context, setContext] = useState("");

  const disabled =
    isSubmitting ||
    !title.trim() ||
    !requesterAgent.trim() ||
    !requesterSolution.trim();

  const submit = () => {
    if (disabled) return;
    onSubmit({
      title: title.trim(),
      requester_agent: requesterAgent.trim(),
      requester_solution: requesterSolution.trim(),
      urgency,
      required_expertise: parseList(expertiseRaw),
      context: context.trim(),
    });
  };

  return (
    <form
      className="space-y-2 rounded border border-slate-200 bg-white p-3"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <h4 className="text-sm font-semibold text-slate-800">
        Create help request
      </h4>
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-slate-600">
          title
          <input
            aria-label="title"
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          urgency
          <select
            aria-label="urgency"
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={urgency}
            onChange={(e) => setUrgency(e.target.value as HelpRequestUrgency)}
          >
            {URGENCIES.map((u) => (
              <option key={u} value={u}>
                {u}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-slate-600">
          requester_agent
          <input
            aria-label="requester_agent"
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={requesterAgent}
            onChange={(e) => setRequesterAgent(e.target.value)}
          />
        </label>
        <label className="text-xs text-slate-600">
          requester_solution
          <input
            aria-label="requester_solution"
            className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm"
            value={requesterSolution}
            onChange={(e) => setRequesterSolution(e.target.value)}
          />
        </label>
      </div>
      <label className="block text-xs text-slate-600">
        required_expertise (comma-separated)
        <input
          aria-label="required_expertise"
          className="mt-0.5 block w-full rounded border border-slate-300 px-2 py-1 text-sm font-mono"
          value={expertiseRaw}
          onChange={(e) => setExpertiseRaw(e.target.value)}
        />
      </label>
      <label className="block text-xs text-slate-600">
        context
        <textarea
          aria-label="context"
          className="mt-0.5 block h-16 w-full rounded border border-slate-300 px-2 py-1 text-sm"
          value={context}
          onChange={(e) => setContext(e.target.value)}
        />
      </label>
      <button
        type="submit"
        className="rounded bg-sky-600 px-3 py-1 text-sm text-white disabled:opacity-50"
        disabled={disabled}
      >
        Create
      </button>
    </form>
  );
}
