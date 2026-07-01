import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Costs from "@/pages/Costs";

// CRITICAL: mock with a factory that preserves the real module — a bare
// vi.mock("@/api/client") auto-mocks every export including the pure
// toDesktopError() helper, silently turning it into a stub that returns
// undefined and breaking the error-banner assertions below.
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    getCostsSummary: vi.fn(),
    getCostsDaily: vi.fn(),
    setCostsBudget: vi.fn(),
  };
});

const SUMMARY = {
  total_cost_usd: 1.5,
  total_calls: 10,
  total_input_tokens: 1000,
  total_output_tokens: 500,
  avg_cost_per_call: 0.15,
  by_model: [{ model: "claude-sonnet-4-6", calls: 10, cost: 1.5 }],
  by_solution: [{ solution: "demo", calls: 10, cost: 1.5 }],
  period_days: 30,
  tenant: null,
  solution: null,
};

const DAILY = {
  daily: [{ date: "2026-06-30", calls: 3, cost_usd: 0.5 }],
  count: 1,
  period_days: 30,
};

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Costs />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Costs page", () => {
  beforeEach(() => vi.resetAllMocks());

  it("shows the cost summary and daily breakdown", async () => {
    vi.mocked(client.getCostsSummary).mockResolvedValue(SUMMARY);
    vi.mocked(client.getCostsDaily).mockResolvedValue(DAILY);
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("$1.5000")).toBeInTheDocument(),
    );
    expect(screen.getByText(/claude-sonnet-4-6/i)).toBeInTheDocument();
    expect(screen.getByText("2026-06-30")).toBeInTheDocument();
  });

  it("submits a budget and shows the confirmation", async () => {
    vi.mocked(client.getCostsSummary).mockResolvedValue(SUMMARY);
    vi.mocked(client.getCostsDaily).mockResolvedValue(DAILY);
    vi.mocked(client.setCostsBudget).mockResolvedValue({
      saved: true,
      key: "demo",
      monthly_usd: 50,
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("$1.5000")).toBeInTheDocument(),
    );

    await user.type(screen.getByPlaceholderText(/optional/i), "demo");
    await user.type(screen.getByLabelText(/monthly budget/i), "50");
    await user.click(screen.getByRole("button", { name: /set budget/i }));

    await waitFor(() =>
      expect(client.setCostsBudget).toHaveBeenCalledWith(50, undefined, "demo"),
    );
    await waitFor(() =>
      expect(screen.getByText(/budget set/i)).toBeInTheDocument(),
    );
  });

  it("shows an error banner when the cost summary query fails", async () => {
    vi.mocked(client.getCostsSummary).mockRejectedValue({
      kind: "SolutionUnavailable",
      detail: { message: "no solution loaded" },
    });
    vi.mocked(client.getCostsDaily).mockResolvedValue(DAILY);
    renderPage();

    const alert = await screen.findByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(/no solution loaded/i);
  });

  it("shows an error banner when the budget mutation fails", async () => {
    vi.mocked(client.getCostsSummary).mockResolvedValue(SUMMARY);
    vi.mocked(client.getCostsDaily).mockResolvedValue(DAILY);
    vi.mocked(client.setCostsBudget).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "missing or invalid 'monthly_usd'" },
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("$1.5000")).toBeInTheDocument(),
    );

    await user.type(screen.getByLabelText(/monthly budget/i), "50");
    await user.click(screen.getByRole("button", { name: /set budget/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText(/InvalidParams/i)).toBeInTheDocument();
  });
});
