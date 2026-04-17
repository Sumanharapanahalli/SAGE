import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getCurrentSolution: vi.fn().mockResolvedValue(null),
}));

import { Layout } from "@/components/layout/Layout";

describe("Layout", () => {
  it("renders sidebar, header, and outlet content", () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/approvals"]}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="approvals" element={<div>OUTLET_BODY</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByRole("heading")).toHaveTextContent(/approvals/i);
    expect(screen.getByText("OUTLET_BODY")).toBeInTheDocument();
  });
});
