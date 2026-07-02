import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getCurrentSolution: vi.fn(),
}));

import * as client from "@/api/client";
import { RequireSolution } from "@/components/layout/RequireSolution";

function renderGuarded(initialPath: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/home" element={<div>Home page</div>} />
          <Route element={<RequireSolution />}>
            <Route path="/guarded" element={<div>Guarded content</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("RequireSolution", () => {
  it("renders the guarded route when a solution is active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "starter",
      path: "/solutions/starter",
    });
    renderGuarded("/guarded");
    expect(await screen.findByText("Guarded content")).toBeInTheDocument();
  });

  it("redirects to /home when no solution is active", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    renderGuarded("/guarded");
    expect(await screen.findByText("Home page")).toBeInTheDocument();
  });
});
