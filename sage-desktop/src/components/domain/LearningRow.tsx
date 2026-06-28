import { useState } from "react";

import type { CollectiveLearning } from "@/api/types";

interface Props {
  learning: CollectiveLearning;
  onValidate: (id: string) => void;
  isValidating?: boolean;
}

const PREVIEW_CHARS = 200;

export function LearningRow({ learning, onValidate, isValidating }: Props) {
  const [expanded, setExpanded] = useState(false);
  const needsToggle = learning.content.length > PREVIEW_CHARS;
  const preview = needsToggle
    ? learning.content.slice(0, PREVIEW_CHARS) + "…"
    : learning.content;
  return (
    <article className="border-b border-slate-200 py-3">
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-800">
          {learning.title}
        </h3>
        <button
          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs hover:bg-slate-50 disabled:opacity-50"
          onClick={() => onValidate(learning.id)}
          disabled={isValidating}
          type="button"
        >
          Validate
        </button>
      </header>
      <div className="text-xs text-slate-500">
        <span className="font-mono">
          {learning.author_solution} / {learning.topic}
        </span>
        <span className="ml-2">conf {learning.confidence.toFixed(2)}</span>
        <span className="ml-2">vc {learning.validation_count}</span>
      </div>
      {learning.tags.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {learning.tags.map((t) => (
            <span
              key={t}
              className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-mono text-slate-700"
            >
              {t}
            </span>
          ))}
        </div>
      )}
      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">
        {expanded ? learning.content : preview}
      </p>
      {needsToggle && (
        <button
          className="mt-1 text-xs text-sky-700 hover:underline"
          onClick={() => setExpanded((v) => !v)}
          type="button"
        >
          {expanded ? "▼ collapse" : "▶ expand"}
        </button>
      )}
    </article>
  );
}
