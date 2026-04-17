import clsx from "clsx";

import type { LeaderboardEntry } from "@/api/types";

export interface LeaderboardProps {
  rows: LeaderboardEntry[];
  selectedRole: string | null;
  onSelect: (role: string) => void;
}

export function Leaderboard({
  rows,
  selectedRole,
  onSelect,
}: LeaderboardProps) {
  if (rows.length === 0) {
    return (
      <div className="rounded border border-sage-100 bg-white p-6 text-sm text-slate-500">
        No agents yet. Run a training round to see ratings appear here.
      </div>
    );
  }
  return (
    <table className="w-full border-separate border-spacing-0 text-sm">
      <thead className="text-left text-xs uppercase text-sage-600">
        <tr>
          <th className="border-b border-sage-100 px-3 py-2">Role</th>
          <th className="border-b border-sage-100 px-3 py-2">Rating</th>
          <th className="border-b border-sage-100 px-3 py-2">RD</th>
          <th className="border-b border-sage-100 px-3 py-2">Wins</th>
          <th className="border-b border-sage-100 px-3 py-2">Losses</th>
          <th className="border-b border-sage-100 px-3 py-2">Win %</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr
            key={r.agent_role}
            className={clsx(
              "cursor-pointer hover:bg-sage-50",
              selectedRole === r.agent_role && "bg-sage-100",
            )}
            onClick={() => onSelect(r.agent_role)}
          >
            <td className="border-b border-sage-50 px-3 py-2 font-medium">
              {r.agent_role}
            </td>
            <td className="border-b border-sage-50 px-3 py-2">
              {r.rating.toFixed(1)}
            </td>
            <td className="border-b border-sage-50 px-3 py-2">
              {r.rating_deviation.toFixed(1)}
            </td>
            <td className="border-b border-sage-50 px-3 py-2">{r.wins}</td>
            <td className="border-b border-sage-50 px-3 py-2">{r.losses}</td>
            <td className="border-b border-sage-50 px-3 py-2">
              {Math.round(r.win_rate * 100)}%
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
