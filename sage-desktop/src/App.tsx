import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/layout/Layout";
import { useAppEvents } from "@/hooks/useAppEvents";
import { Agents } from "@/pages/Agents";
import { Approvals } from "@/pages/Approvals";
import { Audit } from "@/pages/Audit";
import Backlog from "@/pages/Backlog";
import Settings from "@/pages/Settings";
import { Status } from "@/pages/Status";

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
            <Route path="approvals" element={<Approvals />} />
            <Route path="agents" element={<Agents />} />
            <Route path="audit" element={<Audit />} />
            <Route path="status" element={<Status />} />
            <Route path="backlog" element={<Backlog />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </AppEvents>
    </QueryClientProvider>
  );
}
