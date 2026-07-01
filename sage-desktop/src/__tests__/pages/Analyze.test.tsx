import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Analyze from "@/pages/Analyze";

// Keep the REAL toDesktopError (a pure passthrough/normalizer) — a bare
// vi.mock("@/api/client") auto-mocks every export, including it, into a
// stub that silently returns undefined, which the page's `!error` check
// then swallows. Only analyzeLog needs mocking.
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, analyzeLog: vi.fn() };
});

const PROPOSAL = {
  trace_id: "t1",
  created_at: "",
  action_type: "analysis",
  risk_class: "INFORMATIONAL",
  reversible: true,
  proposed_by: "desktop-operator",
  description: "[AMBER] disk usage climbing",
  payload: {},
  status: "pending",
  decided_by: null,
  decided_at: null,
  feedback: null,
  expires_at: null,
  required_role: null,
  approved_by: null,
} as any;

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Analyze />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Analyze page", () => {
  beforeEach(() => vi.resetAllMocks());

  it("submits a log entry and shows the resulting proposal", async () => {
    vi.mocked(client.analyzeLog).mockResolvedValue(PROPOSAL);
    renderPage();

    await userEvent.type(
      screen.getByLabelText(/log entry|signal/i),
      "disk at 95%",
    );
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));

    await waitFor(() =>
      expect(client.analyzeLog).toHaveBeenCalledWith("disk at 95%"),
    );
    await waitFor(() =>
      expect(screen.getByText(/disk usage climbing/i)).toBeInTheDocument(),
    );
    // Directs the operator to where the new proposal now lives.
    expect(
      screen.getByRole("link", { name: /view in approvals/i }),
    ).toBeInTheDocument();
  });

  it("does not submit an empty log entry", async () => {
    renderPage();
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(client.analyzeLog).not.toHaveBeenCalled();
  });

  it("shows an error banner when analysis fails", async () => {
    vi.mocked(client.analyzeLog).mockRejectedValue({
      kind: "Other",
      detail: { code: -32000, message: "analysis failed: llm down" },
    });
    renderPage();

    await userEvent.type(screen.getByLabelText(/log entry|signal/i), "x");
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));

    await waitFor(() =>
      expect(screen.getByText(/llm down/i)).toBeInTheDocument(),
    );
  });
});
