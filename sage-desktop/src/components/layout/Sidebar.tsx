import clsx from "clsx";
import { NavLink } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/approvals", label: "Approvals" },
  { to: "/agents", label: "Agents" },
  { to: "/audit", label: "Audit" },
  { to: "/status", label: "Status" },
  { to: "/backlog", label: "Backlog" },
  { to: "/settings", label: "Settings" },
] as const;

export function Sidebar() {
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
    </nav>
  );
}
