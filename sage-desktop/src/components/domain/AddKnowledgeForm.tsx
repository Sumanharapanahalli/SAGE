import { useState } from "react";

interface Pair {
  key: string;
  value: string;
}

interface Props {
  onSubmit: (text: string, metadata: Record<string, string>) => void;
  isSubmitting?: boolean;
  error?: string | null;
}

export function AddKnowledgeForm({ onSubmit, isSubmitting, error }: Props) {
  const [text, setText] = useState("");
  const [pairs, setPairs] = useState<Pair[]>([]);

  const updatePair = (i: number, patch: Partial<Pair>) => {
    setPairs(pairs.map((p, idx) => (idx === i ? { ...p, ...patch } : p)));
  };
  const removePair = (i: number) =>
    setPairs(pairs.filter((_, idx) => idx !== i));
  const addPair = () => setPairs([...pairs, { key: "", value: "" }]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    const meta: Record<string, string> = {};
    for (const p of pairs) {
      const k = p.key.trim();
      if (!k) continue;
      meta[k] = p.value;
    }
    onSubmit(trimmed, meta);
    setText("");
    setPairs([]);
  };

  return (
    <form
      data-testid="add-knowledge-form"
      className="space-y-3 rounded border border-slate-200 bg-white p-4"
      onSubmit={handleSubmit}
    >
      <header className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">Add entry</h3>
        <span className="text-xs text-slate-500">
          Operator edit — bypasses proposal queue
        </span>
      </header>
      <textarea
        aria-label="entry text"
        className="min-h-[96px] w-full rounded border border-slate-300 p-2 text-sm"
        placeholder="Knowledge to remember…"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="space-y-2">
        <span className="text-xs font-medium text-slate-600">Metadata</span>
        {pairs.map((p, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              aria-label={`metadata key ${i + 1}`}
              className="w-32 rounded border border-slate-300 p-1 font-mono text-xs"
              placeholder="key"
              value={p.key}
              onChange={(e) => updatePair(i, { key: e.target.value })}
            />
            <input
              aria-label={`metadata value ${i + 1}`}
              className="flex-1 rounded border border-slate-300 p-1 text-xs"
              placeholder="value"
              value={p.value}
              onChange={(e) => updatePair(i, { value: e.target.value })}
            />
            <button
              type="button"
              aria-label={`remove metadata ${i + 1}`}
              className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
              onClick={() => removePair(i)}
            >
              Remove
            </button>
          </div>
        ))}
        <button
          type="button"
          className="rounded border border-dashed border-sage-400 px-2 py-1 text-xs text-sage-700 hover:bg-sage-50"
          onClick={addPair}
        >
          + Add metadata pair
        </button>
      </div>
      {error && (
        <p className="text-xs text-rose-700" role="alert">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button
          type="submit"
          disabled={!text.trim() || isSubmitting}
          className="rounded bg-sage-700 px-3 py-1 text-sm text-white hover:bg-sage-800 disabled:bg-slate-300 disabled:text-slate-500"
        >
          {isSubmitting ? "Adding…" : "Add"}
        </button>
      </div>
    </form>
  );
}
