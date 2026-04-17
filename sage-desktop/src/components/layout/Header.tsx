import { useLocation } from "react-router-dom";

const TITLE_MAP: Record<string, string> = {
  "/approvals": "Approvals",
  "/agents": "Agents",
  "/audit": "Audit",
  "/status": "Status",
  "/builds": "Builds",
  "/backlog": "Backlog",
  "/onboarding": "New solution",
  "/yaml": "Edit YAML",
  "/settings": "Settings",
};

export function Header() {
  const location = useLocation();
  const title = TITLE_MAP[location.pathname] ?? "SAGE Desktop";
  return (
    <header className="flex h-14 items-center border-b border-sage-100 bg-white px-6">
      <h1 className="text-lg font-semibold text-sage-900">{title}</h1>
    </header>
  );
}
