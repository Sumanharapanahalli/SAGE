import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/layout/Layout";
import { useAppEvents } from "@/hooks/useAppEvents";
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
import Knowledge from "@/pages/Knowledge";
import Onboarding from "@/pages/Onboarding";
import Organization from "@/pages/Organization";
import Settings from "@/pages/Settings";
import SkillsTools from "@/pages/SkillsTools";
import { Status } from "@/pages/Status";
import Workflows from "@/pages/Workflows";
import YamlEdit from "@/pages/YamlEdit";

const queryClient = new QueryClient({
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

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppEvents>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/approvals" replace />} />
            <Route path="analyze" element={<Analyze />} />
            <Route path="approvals" element={<Approvals />} />
            <Route path="agents" element={<Agents />} />
            <Route path="audit" element={<Audit />} />
            <Route path="status" element={<Status />} />
            <Route path="backlog" element={<Backlog />} />
            <Route path="builds" element={<Builds />} />
            <Route path="onboarding" element={<Onboarding />} />
            <Route path="yaml" element={<YamlEdit />} />
            <Route path="constitution" element={<Constitution />} />
            <Route path="knowledge" element={<Knowledge />} />
            <Route path="collective" element={<Collective />} />
            <Route path="compliance" element={<Compliance />} />
            <Route path="costs" element={<Costs />} />
            <Route path="workflows" element={<Workflows />} />
            <Route path="skills" element={<SkillsTools />} />
            <Route path="organization" element={<Organization />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </AppEvents>
    </QueryClientProvider>
  );
}
