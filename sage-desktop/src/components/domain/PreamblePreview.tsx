interface Props {
  preamble: string;
}

export function PreamblePreview({ preamble }: Props) {
  return (
    <section className="space-y-2" data-testid="preamble-preview">
      <header>
        <h3 className="text-sm font-semibold">Preamble</h3>
        <p className="text-xs text-slate-500">
          This block is prepended to every agent's system prompt.
        </p>
      </header>
      <pre className="max-h-80 overflow-auto rounded border border-slate-200 bg-slate-50 p-3 font-mono text-xs text-slate-800">
        {preamble || "(empty constitution — preamble is omitted)"}
      </pre>
    </section>
  );
}
