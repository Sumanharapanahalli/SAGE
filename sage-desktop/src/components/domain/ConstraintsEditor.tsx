interface Props {
  constraints: string[];
  onChange: (next: string[]) => void;
}

export function ConstraintsEditor({ constraints, onChange }: Props) {
  const update = (i: number, text: string) => {
    onChange(constraints.map((c, idx) => (idx === i ? text : c)));
  };
  const remove = (i: number) => {
    onChange(constraints.filter((_, idx) => idx !== i));
  };
  const add = () => {
    onChange([...constraints, ""]);
  };

  return (
    <section className="space-y-3" data-testid="constraints-editor">
      <header className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold">Constraints</h3>
        <span className="text-xs text-slate-500">
          {constraints.length} hard rules — checked by the action checker
        </span>
      </header>
      <ul className="space-y-2">
        {constraints.map((c, i) => (
          <li
            key={i}
            className="flex gap-2 rounded border border-slate-200 bg-white p-3"
          >
            <input
              aria-label={`constraint ${i + 1}`}
              className="w-full flex-1 rounded border border-slate-300 p-1 text-sm"
              value={c}
              onChange={(e) => update(i, e.target.value)}
            />
            <button
              type="button"
              aria-label={`remove constraint ${i + 1}`}
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
        + Add constraint
      </button>
    </section>
  );
}
