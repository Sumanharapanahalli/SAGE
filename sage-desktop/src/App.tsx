import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/layout/Layout";
import { RequireSolution } from "@/components/layout/RequireSolution";
import { useAppEvents } from "@/hooks/useAppEvents";
import { useCurrentSolution } from "@/hooks/useSolutions";
import Analyze from "@/pages/Analyze";
import { Agents } from "@/pages/Agents";
import { Approvals } from "@/pages/Approvals";
import { Audit } from "@/pages/Audit";
import Backlog from "@/pages/Backlog";
import Builds from "@/pages/Builds";
import Collective from "@/pages/Collective";
import Compliance from "@/pages/Compliance";
import Constitution from "@/pages/Constitution";
import Costs from "@/pages/Costs";
import Eval from "@/pages/Eval";
import Goals from "@/pages/Goals";
import Hil from "@/pages/Hil";
import Home from "@/pages/Home";
import Knowledge from "@/pages/Knowledge";
import Monitor from "@/pages/Monitor";
import Onboarding from "@/pages/Onboarding";
import Organization from "@/pages/Organization";
import Settings from "@/pages/Settings";
import SkillsTools from "@/pages/SkillsTools";
import { Status } from "@/pages/Status";
import Workflows from "@/pages/Workflows";
import YamlEdit from "@/pages/YamlEdit";

// Exported (not just module-local) so tests can call queryClient.clear()
// between scenarios — this singleton otherwise persists cached query data
// (e.g. the current-solution result, staleTime: Infinity) across every
// render in the same test file, including renders in different `it()`s.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Sidecar is local; retry lightly on transient errors (e.g. respawn window)
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppEvents({ children }: PropsWithChildren) {
  useAppEvents();
  return <>{children}</>;
}

/**
 * Index route: send an already-loaded solution straight to its Approvals
 * inbox (today's behavior, preserved for CLI-launched solutions); send a
 * solution-independent boot to Home to pick one. Renders nothing while the
 * initial current-solution fetch is in flight, to avoid a flash redirect.
 */
function IndexRedirect() {
  const { data, isLoading } = useCurrentSolution();
  if (isLoading) return null;
  return <Navigate to={data ? "/approvals" : "/home"} replace />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppEvents>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<IndexRedirect />} />
            <Route path="home" element={<Home />} />
            <Route path="onboarding" element={<Onboarding />} />
            <Route path="organization" element={<Organization />} />
            <Route path="settings" element={<Settings />} />
            <Route element={<RequireSolution />}>
              <Route path="analyze" element={<Analyze />} />
              <Route path="approvals" element={<Approvals />} />
              <Route path="agents" element={<Agents />} />
              <Route path="audit" element={<Audit />} />
              <Route path="status" element={<Status />} />
              <Route path="backlog" element={<Backlog />} />
              <Route path="builds" element={<Builds />} />
              <Route path="yaml" element={<YamlEdit />} />
              <Route path="constitution" element={<Constitution />} />
              <Route path="knowledge" element={<Knowledge />} />
              <Route path="collective" element={<Collective />} />
              <Route path="compliance" element={<Compliance />} />
              <Route path="costs" element={<Costs />} />
              <Route path="workflows" element={<Workflows />} />
              <Route path="skills" element={<SkillsTools />} />
              <Route path="monitor" element={<Monitor />} />
              <Route path="goals" element={<Goals />} />
              <Route path="eval" element={<Eval />} />
              <Route path="hil" element={<Hil />} />
            </Route>
          </Route>
        </Routes>
      </AppEvents>
    </QueryClientProvider>
  );
}
