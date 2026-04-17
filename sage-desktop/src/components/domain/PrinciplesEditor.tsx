import type { ConstitutionPrinciple } from "@/api/types";

interface Props {
  principles: ConstitutionPrinciple[];
  onChange: (next: ConstitutionPrinciple[]) => void;
}

const clampWeight = (w: number): number => {
  if (Number.isNaN(w)) return 0;
  if (w < 0) return 0;
  if (w > 1) return 1;
  return w;
};

export function PrinciplesEditor({ principles, onChange }: Props) {
  const update = (i: number, patch: Partial<ConstitutionPrinciple>) => {
    const next = principles.map((p, idx) => (idx === i ? { ...p, ...patch } : p));
    onChange(next);
  };
  const remove = (i: number) => {
    onChange(principles.filter((_, idx) => idx !== i));
  };
  const add = () => {
    const n = principles.length + 1;
    onChange([
      ...principles,
      { id: `p${n}`, text: "", weight: 0.5 },
    ]);
  };

  return (
    <section className="space-y-3" data-testid="principles-editor">
      <header className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">Principles</h3>
        <span className="text-xs text-slate-500">
          {principles.length} total, weight 0.0–1.0 (1.0 = non-negotiable)
        </span>
      </header>
      <ul className="space-y-2">
        {principles.map((p, i) => (
          <li
            key={i}
            className="flex flex-col gap-2 rounded border border-slate-200 bg-white p-3 sm:flex-row sm:items-start"
          >
            <input
              aria-label={`principle ${i + 1} id`}
              className="w-full rounded border border-slate-300 p-1 font-mono text-xs sm:w-24"
              value={p.id}
              onChange={(e) => update(i, { id: e.target.value })}
            />
            <input
              aria-label={`principle ${i + 1} text`}
              className="w-full flex-1 rounded border border-slate-300 p-1 text-sm"
              value={p.text}
              onChange={(e) => update(i, { text: e.target.value })}
            />
            <label className="flex shrink-0 items-center gap-1 text-xs text-slate-600">
              weight
              <input
                type="number"
                step={0.05}
                min={0}
                max={1}
                aria-label={`principle ${i + 1} weight`}
                className="w-16 rounded border border-slate-300 p-1 text-right font-mono text-xs"
                value={p.weight}
                onChange={(e) =>
                  update(i, { weight: clampWeight(Number(e.target.value)) })
                }
              />
            </label>
            <button
              type="button"
              aria-label={`remove principle ${i + 1}`}
              className="shrink-0 rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
              onClick={() => remove(i)}
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="rounded border border-dashed border-sage-400 px-3 py-1 text-sm text-sage-700 hover:bg-sage-50"
        onClick={add}
      >
        + Add principle
      </button>
    </section>
  );
}
