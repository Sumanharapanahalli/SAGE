import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Hil from "@/pages/Hil";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    getHilStatus: vi.fn(),
    hilConnect: vi.fn(),
    hilRunSuite: vi.fn(),
    hilReport: vi.fn(),
  };
});

function renderPage() {
  const qc = createTestQueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Hil />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const NOT_CONNECTED = {
  connected: false,
  transport: "none",
  session_id: null,
  tests_run: 0,
  message: "No HIL runner initialised. Call hil.connect to start.",
};

describe("Hil page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.getHilStatus).mockResolvedValue(NOT_CONNECTED);
  });

  it("shows the not-connected status and does not auto-connect", async () => {
    renderPage();
    expect(await screen.findByText(/not connected/i)).toBeInTheDocument();
    expect(client.hilConnect).not.toHaveBeenCalled();
  });

  it("connects on explicit button click with the selected transport", async () => {
    vi.mocked(client.hilConnect).mockResolvedValue({
      transport: "mock",
      connected: true,
      session_id: "hil_1",
      message: "Connected",
    });
    renderPage();
    await screen.findByText(/not connected/i);
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));
    await waitFor(() => expect(client.hilConnect).toHaveBeenCalled());
    expect(client.hilConnect).toHaveBeenCalledWith("mock", {});
  });

  it("runs a suite defined via the JSON test-case editor", async () => {
    vi.mocked(client.hilRunSuite).mockResolvedValue({
      session_id: "hil_1",
      transport: "mock",
      total: 1,
      passed: 1,
      failed: 0,
      errors: 0,
      skipped: 0,
      blocked: 0,
      pass_rate: 100,
      results: [
        {
          test_id: "TC-1",
          test_name: "Power-on",
          requirement_id: "REQ-1",
          verdict: "PASS",
          actual_result: "[MOCK] ok",
          duration_seconds: 0.01,
          timestamp: "2026-07-01T00:00:00Z",
        },
      ],
    });
    renderPage();
    await screen.findByText(/not connected/i);

    const textarea = screen.getByLabelText(/test cases/i);
    fireEvent.change(textarea, {
      target: { value: '[{"id":"TC-1","name":"Power-on","requirement_id":"REQ-1"}]' },
    });
    await userEvent.click(screen.getByRole("button", { name: /run suite/i }));

    expect(await screen.findByText(/1\s*\/\s*1/)).toBeInTheDocument();
    expect(client.hilRunSuite).toHaveBeenCalled();
  });

  it("shows an error when the test-case JSON is invalid", async () => {
    renderPage();
    await screen.findByText(/not connected/i);
    const textarea = screen.getByLabelText(/test cases/i);
    fireEvent.change(textarea, { target: { value: "not json" } });
    await userEvent.click(screen.getByRole("button", { name: /run suite/i }));
    expect(await screen.findByText(/valid json/i)).toBeInTheDocument();
    expect(client.hilRunSuite).not.toHaveBeenCalled();
  });

  it("generates a report for the active session", async () => {
    vi.mocked(client.getHilStatus).mockResolvedValue({
      connected: true,
      transport: "mock",
      session_id: "hil_1",
      tests_run: 1,
      passed: 1,
      failed: 0,
      blocked: 0,
    });
    vi.mocked(client.hilReport).mockResolvedValue({
      report_type: "HIL Test Evidence — IEC62304",
      standard: "IEC62304",
      standard_full_name: "IEC 62304:2015+A1 — Medical Device Software",
      generated_at: "2026-07-01T00:00:00Z",
      session_id: "hil_1",
      transport: "mock",
      evidence_sections: ["§5.5 Unit Testing"],
      pass_criteria: "All safety-class tests must PASS",
      summary: {
        total_tests: 1, passed: 1, failed: 0, blocked: 0,
        pass_rate: 100, overall_status: "PASS",
      },
      traceability: [],
      deviations: [],
      failed_tests: [],
    });
    renderPage();
    await screen.findByText(/hil_1/);
    await userEvent.click(screen.getByRole("button", { name: /generate report/i }));
    expect(await screen.findByText(/IEC 62304/)).toBeInTheDocument();
    expect(client.hilReport).toHaveBeenCalledWith("hil_1", "IEC62304");
  });

  it("shows an error banner when connect fails", async () => {
    vi.mocked(client.hilConnect).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "boom" },
    });
    renderPage();
    await screen.findByText(/not connected/i);
    await userEvent.click(screen.getByRole("button", { name: /connect/i }));
    await waitFor(() => expect(screen.getByText(/boom/i)).toBeInTheDocument());
  });
});
