import clsx from "clsx";
import { NavLink } from "react-router-dom";

import { useApprovals } from "@/hooks/useApprovals";
import { useCurrentSolution } from "@/hooks/useSolutions";

const NAV_ITEMS = [
  { to: "/analyze", label: "Analyze" },
  { to: "/approvals", label: "Approvals" },
  { to: "/agents", label: "Agents" },
  { to: "/audit", label: "Audit" },
  { to: "/activity", label: "Activity" },
  { to: "/regulatory", label: "Regulatory" },
  { to: "/status", label: "Status" },
  { to: "/queue", label: "Queue" },
  { to: "/builds", label: "Builds" },
  { to: "/backlog", label: "Backlog" },
  { to: "/yaml", label: "YAML" },
  { to: "/constitution", label: "Constitution" },
  { to: "/knowledge", label: "Knowledge" },
  { to: "/collective", label: "Collective" },
  { to: "/compliance", label: "Compliance" },
  { to: "/costs", label: "Costs" },
  { to: "/workflows", label: "Workflows" },
  { to: "/skills", label: "Skills & Tools" },
  { to: "/organization", label: "Organization" },
  { to: "/monitor", label: "Monitor" },
  { to: "/goals", label: "Goals" },
  { to: "/eval", label: "Eval" },
  { to: "/hil", label: "HIL" },
  { to: "/console", label: "Console" },
  { to: "/settings", label: "Settings" },
] as const;

export function Sidebar() {
  const { data: current } = useCurrentSolution();
  const { data: pending } = useApprovals();
  const pendingCount = pending?.length ?? 0;
  const hasSolution = Boolean(current);

  return (
    <nav className="flex w-56 shrink-0 flex-col overflow-y-auto border-r border-sage-100 bg-sage-50 p-4">
      <div className="mb-4 text-xl font-semibold text-sage-700">SAGE</div>

      <NavLink
        to="/home"
        data-testid="sidebar-solution"
        className="mb-4 block rounded border border-sage-200 bg-white px-3 py-2 text-xs hover:border-sage-400 hover:bg-sage-50"
      >
        <div className="uppercase tracking-wide text-sage-700">Solution</div>
        <div
          className="mt-0.5 truncate font-medium text-sage-900"
          title={current?.name ?? "none"}
        >
          {current?.name ?? "Pick a solution…"}
        </div>
      </NavLink>

      {hasSolution && (
        <ul className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  clsx(
                    "flex items-center rounded px-3 py-2 text-sm transition-colors",
                    isActive
                      ? "bg-sage-500 text-white"
                      : "text-sage-900 hover:bg-sage-100",
                  )
                }
              >
                <span>{item.label}</span>
                {item.to === "/approvals" && pendingCount > 0 && (
                  <span
                    data-testid="pending-badge"
                    className="ml-auto rounded-full bg-red-600 px-2 py-0.5 text-xs font-semibold text-white"
                  >
                    {pendingCount}
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      )}

      {/* "+ New solution" deliberately does NOT live here. It is the primary action of the
          solution picker (Home), and rendering it in both places put the same call to action
          on screen twice whenever the picker was open. */}
    </nav>
  );
}
