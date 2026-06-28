import type { ConstitutionDecisions } from "@/api/types";

interface Props {
  decisions: ConstitutionDecisions | undefined;
  onChange: (next: ConstitutionDecisions) => void;
}

type Key = "auto_approve_categories" | "escalation_keywords";

const LABELS: Record<Key, { title: string; help: string; add: string }> = {
  auto_approve_categories: {
    title: "Auto-approve categories",
    help: "Action categories that bypass the approval queue.",
    add: "+ Add category",
  },
  escalation_keywords: {
    title: "Escalation keywords",
    help: "Words that force escalation to a human reviewer.",
    add: "+ Add keyword",
  },
};

export function DecisionsEditor({ decisions, onChange }: Props) {
  const updateList = (key: Key, next: string[]) =>
    onChange({ ...decisions, [key]: next });

  const renderList = (key: Key) => {
    const items = decisions?.[key] ?? [];
    const meta = LABELS[key];
    return (
      <div key={key}>
        <span className="block text-xs font-medium">{meta.title}</span>
        <p className="text-xs text-slate-500">{meta.help}</p>
        <ul className="mt-1 space-y-1">
          {items.map((v, i) => (
            <li key={i} className="flex gap-2">
              <input
                aria-label={`${key} ${i + 1}`}
                className="flex-1 rounded border border-slate-300 p-1 text-sm"
                value={v}
                onChange={(e) =>
                  updateList(
                    key,
                    items.map((x, idx) => (idx === i ? e.target.value : x)),
                  )
                }
              />
              <button
                type="button"
                aria-label={`remove ${key} ${i + 1}`}
                className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
                onClick={() =>
                  updateList(
                    key,
                    items.filter((_, idx) => idx !== i),
                  )
                }
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="mt-2 rounded border border-dashed border-sage-400 px-3 py-1 text-sm text-sage-700 hover:bg-sage-50"
          onClick={() => updateList(key, [...items, ""])}
        >
          {meta.add}
        </button>
      </div>
    );
  };

  return (
    <section className="space-y-4" data-testid="decisions-editor">
      <header>
        <h3 className="text-sm font-semibold">Decisions</h3>
      </header>
      {renderList("auto_approve_categories")}
      {renderList("escalation_keywords")}
    </section>
  );
}
