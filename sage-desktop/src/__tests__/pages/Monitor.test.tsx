import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Monitor from "@/pages/Monitor";

// CRITICAL: a bare `vi.mock("@/api/client")` with no factory auto-mocks
// EVERY export, including the pure `toDesktopError` helper used by
// ErrorBanner's consumers — silently breaking error-banner assertions. Keep
// the real module and only stub the two calls this page uses.
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    getMonitorStatus: vi.fn(),
    getSchedulerStatus: vi.fn(),
  };
});

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Monitor />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Monitor page", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renders the monitor agent's active thread status", async () => {
    vi.mocked(client.getMonitorStatus).mockResolvedValue({
      running: true,
      active_threads: ["MonitorAgent-Teams"],
      thread_count: 1,
      seen_messages: 3,
      seen_issues: 0,
      teams_configured: true,
      metabase_configured: false,
      gitlab_configured: false,
    });
    vi.mocked(client.getSchedulerStatus).mockResolvedValue({
      running: false,
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/MonitorAgent-Teams/)).toBeInTheDocument(),
    );
    expect(screen.getAllByText(/1/).length).toBeGreaterThan(0);
  });

  it("renders the scheduler's running state and schedule count", async () => {
    vi.mocked(client.getMonitorStatus).mockResolvedValue({ running: false });
    vi.mocked(client.getSchedulerStatus).mockResolvedValue({
      running: true,
      scheduled_count: 4,
      next_check_in_seconds: 30,
    });
    renderPage();

    await waitFor(() => expect(screen.getByText("4")).toBeInTheDocument());
  });

  it("shows a clean not-active message (not an error banner) when the monitor is unavailable", async () => {
    vi.mocked(client.getMonitorStatus).mockResolvedValue({
      running: false,
      error: "monitor thread crashed",
    });
    vi.mocked(client.getSchedulerStatus).mockResolvedValue({ running: false });
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/not active/i)).toBeInTheDocument(),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a clean not-active message (not an error banner) when the scheduler is unavailable", async () => {
    vi.mocked(client.getMonitorStatus).mockResolvedValue({ running: false });
    vi.mocked(client.getSchedulerStatus).mockResolvedValue({
      running: false,
      error: "no project loaded",
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getAllByText(/not active/i).length).toBe(2),
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an error banner on a genuine transport failure", async () => {
    vi.mocked(client.getMonitorStatus).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "stream closed" },
    });
    vi.mocked(client.getSchedulerStatus).mockResolvedValue({ running: false });
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i),
    );
  });
});
