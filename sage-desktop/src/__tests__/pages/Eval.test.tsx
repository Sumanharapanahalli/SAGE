import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Eval from "@/pages/Eval";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listEvalSuites: vi.fn(),
    runEval: vi.fn(),
    getEvalHistory: vi.fn(),
  };
});

function renderPage() {
  const qc = createTestQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Eval />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Eval page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.getEvalHistory).mockResolvedValue({ history: [], count: 0 });
  });

  it("lists available suites", async () => {
    vi.mocked(client.listEvalSuites).mockResolvedValue({
      suites: ["smoke", "regression"],
      count: 2,
    });
    renderPage();
    expect(await screen.findByText("smoke")).toBeInTheDocument();
    expect(screen.getByText("regression")).toBeInTheDocument();
  });

  it("shows an empty state when there are no suites", async () => {
    vi.mocked(client.listEvalSuites).mockResolvedValue({ suites: [], count: 0 });
    renderPage();
    expect(await screen.findByText(/no eval suites/i)).toBeInTheDocument();
  });

  it("runs a suite and shows the result summary", async () => {
    vi.mocked(client.listEvalSuites).mockResolvedValue({
      suites: ["smoke"],
      count: 1,
    });
    vi.mocked(client.runEval).mockResolvedValue({
      run_id: "r1",
      suite: "smoke",
      total_cases: 4,
      passed_cases: 3,
      failed_cases: 1,
      mean_score: 8.5,
      results: [],
    });
    renderPage();
    await screen.findByText("smoke");
    await userEvent.click(screen.getByRole("button", { name: /run/i }));
    expect(await screen.findByText(/3\s*\/\s*4/)).toBeInTheDocument();
    expect(client.runEval).toHaveBeenCalledWith("smoke");
  });

  it("renders history entries", async () => {
    vi.mocked(client.listEvalSuites).mockResolvedValue({ suites: [], count: 0 });
    vi.mocked(client.getEvalHistory).mockResolvedValue({
      history: [
        {
          run_id: "r1",
          suite: "smoke",
          started_at: "2026-06-30T00:00:00Z",
          total_cases: 4,
          passed_cases: 3,
          mean_score: 8.5,
        },
      ],
      count: 1,
    });
    renderPage();
    expect(await screen.findByText("r1")).toBeInTheDocument();
  });

  it("shows an error banner when the suites list fails", async () => {
    vi.mocked(client.listEvalSuites).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "boom" },
    });
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/boom/i)).toBeInTheDocument(),
    );
  });
});
