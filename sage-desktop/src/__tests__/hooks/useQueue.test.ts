import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import { useQueueStatus, useQueueTasks } from "@/hooks/useQueue";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useQueueStatus", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches queue status counts", async () => {
    vi.mocked(client.getQueueStatus).mockResolvedValue({
      pending: 2, in_progress: 1, done: 3, failed: 0, blocked: 0,
      parallel_enabled: true, max_workers: 4,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useQueueStatus(), { wrapper: wrapperWith(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.pending).toBe(2);
  });
});

describe("useQueueTasks", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists queue tasks with filters", async () => {
    vi.mocked(client.listQueueTasks).mockResolvedValue([]);
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useQueueTasks({ status: "pending" }), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.listQueueTasks).toHaveBeenCalledWith({ status: "pending" });
  });
});
