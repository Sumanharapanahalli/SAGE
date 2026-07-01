import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import { useMonitorStatus, useSchedulerStatus } from "@/hooks/useMonitor";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useMonitorStatus", () => {
  beforeEach(() => vi.resetAllMocks());

  it("returns the monitor agent's polling status", async () => {
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
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useMonitorStatus(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.running).toBe(true);
    expect(result.current.data?.thread_count).toBe(1);
  });

  it("resolves (does not reject) with a not-running shape when the monitor is unavailable", async () => {
    vi.mocked(client.getMonitorStatus).mockResolvedValue({
      running: false,
      error: "monitor thread crashed",
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useMonitorStatus(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.running).toBe(false);
    expect(result.current.isError).toBe(false);
  });
});

describe("useSchedulerStatus", () => {
  beforeEach(() => vi.resetAllMocks());

  it("returns the task scheduler's running state and schedule count", async () => {
    vi.mocked(client.getSchedulerStatus).mockResolvedValue({
      running: true,
      scheduled_count: 2,
      next_check_in_seconds: 30,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useSchedulerStatus(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.scheduled_count).toBe(2);
  });

  it("resolves (does not reject) with a not-running shape when the scheduler is unavailable", async () => {
    vi.mocked(client.getSchedulerStatus).mockResolvedValue({
      running: false,
      error: "no project loaded",
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useSchedulerStatus(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.running).toBe(false);
    expect(result.current.isError).toBe(false);
  });
});
