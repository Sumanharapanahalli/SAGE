import clsx from "clsx";

import type { Agent } from "@/api/types";

interface Props {
  agent: Agent;
  selected?: boolean;
  onSelect?: (name: string) => void;
}

export function AgentCard({ agent, selected, onSelect }: Props) {
  const lastActive = agent.last_active
    ? new Date(agent.last_active).toLocaleString()
    : "never";
  return (
    <article
      className={clsx(
        "rounded-lg border bg-white p-4 shadow-sm",
        selected ? "border-sage-400 ring-1 ring-sage-300" : "border-sage-100",
      )}
    >
      <header className="mb-2 flex items-center gap-2">
        <h3 className="text-base font-semibold text-sage-900">{agent.name}</h3>
        <span
          className={clsx(
            "rounded px-2 py-0.5 text-xs font-semibold uppercase",
            agent.kind === "core"
              ? "bg-sage-100 text-sage-700"
              : "bg-violet-100 text-violet-700",
          )}
        >
          {agent.kind}
        </span>
      </header>
      <p className="mb-3 text-sm text-slate-700">{agent.description}</p>
      <dl className="grid grid-cols-2 gap-2 text-xs text-slate-500">
        <div>
          <dt className="font-medium text-slate-400">Events</dt>
          <dd className="text-sage-900">{agent.event_count}</dd>
        </div>
        <div>
          <dt className="font-medium text-slate-400">Last active</dt>
          <dd className="text-sage-900">{lastActive}</dd>
        </div>
      </dl>
      {onSelect && (
        <button
          type="button"
          className="mt-3 text-xs font-medium text-sage-700 hover:underline"
          onClick={() => onSelect(agent.name)}
        >
          View performance
        </button>
      )}
    </article>
  );
}
