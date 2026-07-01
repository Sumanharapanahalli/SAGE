import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getCurrentSolution: vi.fn().mockResolvedValue(null),
}));

import { Sidebar } from "@/components/layout/Sidebar";

function renderAt(path: string) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Sidebar", () => {
  it("renders the four Phase 1 nav entries", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /approvals/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /agents/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /audit/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /status/i })).toBeInTheDocument();
  });

  it("marks the active route with aria-current=page", () => {
    renderAt("/audit");
    const link = screen.getByRole("link", { name: /audit/i });
    expect(link).toHaveAttribute("aria-current", "page");
  });

  it("renders a solution footer", () => {
    renderAt("/approvals");
    expect(screen.getByTestId("sidebar-solution")).toHaveTextContent(/solution/i);
  });

  it("includes the Constitution entry (Phase 5b)", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /constitution/i }),
    ).toHaveAttribute("href", "/constitution");
  });

  it("includes the Knowledge entry (Phase 5c)", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /knowledge/i }),
    ).toHaveAttribute("href", "/knowledge");
  });

  it("includes the Collective entry (Phase 5a)", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /collective/i }),
    ).toHaveAttribute("href", "/collective");
  });

  it("includes the Analyze entry — the SURFACE -> PROPOSE trigger", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /analyze/i }),
    ).toHaveAttribute("href", "/analyze");
  });

  it("includes the Compliance entry (Phase 5f)", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /compliance/i }),
    ).toHaveAttribute("href", "/compliance");
  });

  it("includes the Costs entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /costs/i })).toHaveAttribute(
      "href",
      "/costs",
    );
  });

  it("includes the Workflows entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /workflows/i })).toHaveAttribute(
      "href",
      "/workflows",
    );
  });

  it("includes the Skills & Tools entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /skills/i })).toHaveAttribute(
      "href",
      "/skills",
    );
  });

  it("includes the Organization entry", () => {
    renderAt("/approvals");
    expect(
      screen.getByRole("link", { name: /organization/i }),
    ).toHaveAttribute("href", "/organization");
  });

  it("includes the Monitor entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /monitor/i })).toHaveAttribute(
      "href",
      "/monitor",
    );
  });

  it("includes the Goals entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /goals/i })).toHaveAttribute(
      "href",
      "/goals",
    );
  });

  it("includes the Eval entry", () => {
    renderAt("/approvals");
    expect(screen.getByRole("link", { name: /eval/i })).toHaveAttribute(
      "href",
      "/eval",
    );
  });
});
