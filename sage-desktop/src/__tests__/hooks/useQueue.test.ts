import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import {
  useCancelQueueTask,
  useQueueStatus,
  useQueueTasks,
  useRetryQueueTask,
} from "@/hooks/useQueue";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useQueueStatus", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches queue status counts", async () => {
    vi.mocked(client.getQueueStatus).mockResolvedValue({
      pending: 2, in_progress: 1, completed: 3, failed: 0, blocked: 0, cancelled: 0,
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

describe("useCancelQueueTask", () => {
  beforeEach(() => vi.resetAllMocks());

  it("cancels a task and invalidates the queue cache", async () => {
    vi.mocked(client.cancelQueueTask).mockResolvedValue({
      cancelled: true, status: "cancelled", was_running: false,
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useCancelQueueTask(), {
      wrapper: wrapperWith(qc),
    });

    await act(async () => {
      await result.current.mutateAsync("t1");
    });

    expect(client.cancelQueueTask).toHaveBeenCalledWith("t1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["queue"] });
  });
});

describe("useRetryQueueTask", () => {
  beforeEach(() => vi.resetAllMocks());

  it("re-queues a task and invalidates the queue cache", async () => {
    vi.mocked(client.retryQueueTask).mockResolvedValue({
      requeued: true, status: "pending",
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useRetryQueueTask(), {
      wrapper: wrapperWith(qc),
    });

    await act(async () => {
      await result.current.mutateAsync("t1");
    });

    expect(client.retryQueueTask).toHaveBeenCalledWith("t1");
    expect(spy).toHaveBeenCalledWith({ queryKey: ["queue"] });
  });
});
