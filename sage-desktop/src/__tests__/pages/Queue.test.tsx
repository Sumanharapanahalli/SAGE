import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import Queue from "@/pages/Queue";
import type { QueueTask } from "@/api/types";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

const STATUS = {
  pending: 1,
  in_progress: 0,
  completed: 0,
  cancelled: 0,
  failed: 1,
  blocked: 0,
  parallel_enabled: false,
  max_workers: 0,
};

function task(overrides: Partial<QueueTask> = {}): QueueTask {
  return {
    task_id: "task-abcdef123",
    task_type: "ANALYZE_LOG",
    status: "failed",
    priority: 5,
    created_at: "2026-04-17T12:00:00Z",
    error: "ValueError: bad payload",
    retry_count: 1,
    max_retries: 3,
    ...overrides,
  };
}

function renderQueue() {
  const qc = createTestQueryClient();
  const Wrapper = wrapperWith(qc);
  return render(
    <Wrapper>
      <MemoryRouter>
        <Queue />
      </MemoryRouter>
    </Wrapper>,
  );
}

describe("Queue page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.getQueueStatus).mockResolvedValue(STATUS);
  });

  it("lists tasks from the queue", async () => {
    vi.mocked(client.listQueueTasks).mockResolvedValue([task()]);
    renderQueue();
    expect(await screen.findByText("ANALYZE_LOG")).toBeInTheDocument();
    expect(screen.getByText(/ValueError: bad payload/)).toBeInTheDocument();
  });

  it("cancels a pending task through the operator RPC", async () => {
    vi.mocked(client.listQueueTasks).mockResolvedValue([
      task({ status: "pending", error: null }),
    ]);
    vi.mocked(client.cancelQueueTask).mockResolvedValue({
      cancelled: true,
      status: "cancelled",
      was_running: false,
    });

    renderQueue();
    fireEvent.click(
      await screen.findByRole("button", { name: /cancel task task-abcdef123/i }),
    );

    await waitFor(() =>
      expect(client.cancelQueueTask).toHaveBeenCalledWith("task-abcdef123"),
    );
    expect(
      await screen.findByText(/cancelled before dispatch/i),
    ).toBeInTheDocument();
  });

  it("says plainly that cancelling a RUNNING task does not kill it", async () => {
    // The queue has no cooperative cancellation. Reporting a flat "cancelled"
    // for an in-flight task would tell the operator a job stopped when it did not.
    vi.mocked(client.listQueueTasks).mockResolvedValue([
      task({ status: "in_progress", error: null }),
    ]);
    vi.mocked(client.cancelQueueTask).mockResolvedValue({
      cancelled: true,
      status: "cancelled",
      was_running: true,
    });

    renderQueue();
    fireEvent.click(
      await screen.findByRole("button", { name: /cancel task task-abcdef123/i }),
    );

    expect(await screen.findByText(/is not killed/i)).toBeInTheDocument();
  });

  it("retries a failed task through the operator RPC", async () => {
    vi.mocked(client.listQueueTasks).mockResolvedValue([task()]);
    vi.mocked(client.retryQueueTask).mockResolvedValue({
      requeued: true,
      status: "pending",
    });

    renderQueue();
    fireEvent.click(
      await screen.findByRole("button", { name: /retry task task-abcdef123/i }),
    );

    await waitFor(() =>
      expect(client.retryQueueTask).toHaveBeenCalledWith("task-abcdef123"),
    );
    expect(await screen.findByText(/re-queued as pending/i)).toBeInTheDocument();
  });

  it("does not offer retry on a completed task, nor cancel on a failed one", async () => {
    vi.mocked(client.listQueueTasks).mockResolvedValue([
      task({ status: "completed", task_id: "done-1", error: null }),
      task({ status: "failed", task_id: "failed-1" }),
    ]);
    renderQueue();
    await screen.findAllByText("ANALYZE_LOG");

    // Row "done-1" = completed: neither action applies.
    expect(
      screen.getByRole("button", { name: /cancel task done-1/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /retry task done-1/i }),
    ).toBeDisabled();
    // Row "failed-1": cancel is meaningless, retry is the recovery.
    expect(
      screen.getByRole("button", { name: /cancel task failed-1/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /retry task failed-1/i }),
    ).toBeEnabled();
  });

  it("surfaces a typed error when the operator action is refused", async () => {
    vi.mocked(client.listQueueTasks).mockResolvedValue([task()]);
    vi.mocked(client.retryQueueTask).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "Task 'x' is completed — only failed, cancelled, or blocked tasks can be retried" },
    });

    renderQueue();
    fireEvent.click(
      await screen.findByRole("button", { name: /retry task task-abcdef123/i }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(/InvalidParams/);
  });
});
