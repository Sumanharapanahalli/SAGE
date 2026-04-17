import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "@/components/layout/Layout";
import { Agents } from "@/pages/Agents";
import { Approvals } from "@/pages/Approvals";
import { Audit } from "@/pages/Audit";
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

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/approvals" replace />} />
          <Route path="approvals" element={<Approvals />} />
          <Route path="agents" element={<Agents />} />
          <Route path="audit" element={<Audit />} />
          <Route path="status" element={<Status />} />
        </Route>
      </Routes>
    </QueryClientProvider>
  );
}
