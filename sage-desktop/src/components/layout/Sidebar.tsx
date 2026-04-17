import clsx from "clsx";
import { NavLink } from "react-router-dom";

import { useCurrentSolution } from "@/hooks/useSolutions";

const NAV_ITEMS = [
  { to: "/approvals", label: "Approvals" },
  { to: "/agents", label: "Agents" },
  { to: "/audit", label: "Audit" },
  { to: "/status", label: "Status" },
  { to: "/builds", label: "Builds" },
  { to: "/backlog", label: "Backlog" },
  { to: "/yaml", label: "YAML" },
  { to: "/constitution", label: "Constitution" },
  { to: "/knowledge", label: "Knowledge" },
  { to: "/settings", label: "Settings" },
] as const;

export function Sidebar() {
  const { data: current } = useCurrentSolution();
  const label = current?.name ?? "none";
  return (
    <nav className="flex w-56 shrink-0 flex-col border-r border-sage-100 bg-sage-50 p-4">
      <div className="mb-6 text-xl font-semibold text-sage-700">SAGE</div>
      <ul className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  "block rounded px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-sage-500 text-white"
                    : "text-sage-900 hover:bg-sage-100",
                )
              }
            >
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="mt-auto">
        <NavLink
          to="/onboarding"
          className="block rounded border border-dashed border-sage-400 px-3 py-2 text-center text-sm text-sage-700 hover:bg-sage-100"
        >
          + New solution
        </NavLink>
        <div className="pt-4 text-xs text-sage-700" data-testid="sidebar-solution">
          <div className="uppercase tracking-wide text-sage-500">Solution</div>
          <div className="mt-0.5 truncate font-medium" title={label}>
            {label}
          </div>
          <NavLink
            to="/settings#solution"
            className="mt-1 inline-block text-[11px] text-sage-600 underline-offset-2 hover:underline"
          >
            Switch…
          </NavLink>
        </div>
      </div>
    </nav>
  );
}
