import { useState } from "react";

import type { AnalyticsResult } from "@/api/types";

interface Props {
  data: AnalyticsResult | undefined;
  isLoading: boolean;
  role: string | null;
}

export function Analytics({ data, isLoading, role }: Props) {
  const [open, setOpen] = useState(false);

  if (!role) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-sm text-slate-500">
        Select an agent from the leaderboard to see analytics.
      </div>
    );
  }
  if (isLoading) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-sm text-slate-500">
        Loading analytics for {role}…
      </div>
    );
  }
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-sm text-slate-500">
        No analytics available for {role}.
      </div>
    );
  }

  return (
    <div className="rounded border border-sage-100 bg-white">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium hover:bg-sage-50"
      >
        <span>Analytics for {role}</span>
        <span aria-hidden>{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <pre className="max-h-96 overflow-auto border-t border-sage-100 bg-slate-50 p-3 text-xs">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  );
}
