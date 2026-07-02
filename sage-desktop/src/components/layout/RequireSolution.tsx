import { Navigate, Outlet } from "react-router-dom";

import { useCurrentSolution } from "@/hooks/useSolutions";

/**
 * Route guard for solution-scoped pages. Redirects to /home when no
 * solution is loaded. Renders nothing while the initial current-solution
 * fetch is in flight, to avoid a flash-redirect before it resolves.
 */
export function RequireSolution() {
  const { data, isLoading } = useCurrentSolution();

  if (isLoading) return null;
  if (!data) return <Navigate to="/home" replace />;
  return <Outlet />;
}
