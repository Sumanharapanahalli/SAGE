import type { QueueStatus } from "@/api/types";

interface Props { status: QueueStatus; }

// Keys MUST be the literal values TaskStatus emits. The tile used to read
// "done" — a status the framework never produces — so the Done cell rendered
// blank regardless of how many tasks had finished.
const CELLS: [keyof QueueStatus, string][] = [
  ["pending", "Pending"],
  ["in_progress", "In progress"],
  ["completed", "Completed"],
  ["failed", "Failed"],
  ["blocked", "Blocked"],
  ["cancelled", "Cancelled"],
];

export function QueueTile({ status }: Props) {
  return (
    <section className="rounded border border-gray-200 p-4">
      <h3 className="mb-3 text-sm font-semibold">Task queue</h3>
      <dl className="grid grid-cols-6 gap-4 text-center">
        {CELLS.map(([key, label]) => (
          <div key={key}>
            <dt className="text-xs uppercase text-gray-500">{label}</dt>
            <dd className="text-2xl font-semibold">{status[key] as number}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-gray-500">
        {status.parallel_enabled
          ? `Parallel: max ${status.max_workers} workers`
          : "Parallel disabled"}
      </p>
    </section>
  );
}
