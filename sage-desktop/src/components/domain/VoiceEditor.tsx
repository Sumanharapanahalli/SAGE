import type { ConstitutionVoice } from "@/api/types";

interface Props {
  voice: ConstitutionVoice | undefined;
  onChange: (next: ConstitutionVoice) => void;
}

export function VoiceEditor({ voice, onChange }: Props) {
  const tone = voice?.tone ?? "";
  const avoid = voice?.avoid ?? [];

  const setTone = (v: string) => onChange({ ...voice, tone: v });
  const setAvoid = (i: number, v: string) =>
    onChange({
      ...voice,
      avoid: avoid.map((x, idx) => (idx === i ? v : x)),
    });
  const addAvoid = () => onChange({ ...voice, avoid: [...avoid, ""] });
  const removeAvoid = (i: number) =>
    onChange({ ...voice, avoid: avoid.filter((_, idx) => idx !== i) });

  return (
    <section className="space-y-3" data-testid="voice-editor">
      <header>
        <h3 className="text-sm font-semibold">Voice</h3>
        <p className="text-xs text-slate-500">
          Stylistic guidance injected into every agent preamble.
        </p>
      </header>
      <label className="block">
        <span className="block text-xs font-medium">Tone</span>
        <input
          aria-label="voice tone"
          className="mt-1 w-full rounded border border-slate-300 p-1 text-sm"
          value={tone}
          onChange={(e) => setTone(e.target.value)}
          placeholder="e.g. precise, technical, terse"
        />
      </label>
      <div>
        <span className="block text-xs font-medium">Avoid</span>
        <ul className="mt-1 space-y-1">
          {avoid.map((a, i) => (
            <li key={i} className="flex gap-2">
              <input
                aria-label={`avoid ${i + 1}`}
                className="flex-1 rounded border border-slate-300 p-1 text-sm"
                value={a}
                onChange={(e) => setAvoid(i, e.target.value)}
              />
              <button
                type="button"
                aria-label={`remove avoid ${i + 1}`}
                className="rounded border border-slate-300 px-2 py-1 text-xs text-slate-700 hover:bg-slate-100"
                onClick={() => removeAvoid(i)}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          className="mt-2 rounded border border-dashed border-sage-400 px-3 py-1 text-sm text-sage-700 hover:bg-sage-50"
          onClick={addAvoid}
        >
          + Add phrase to avoid
        </button>
      </div>
    </section>
  );
}
