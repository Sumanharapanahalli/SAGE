import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listActivity: vi.fn(),
}));

import * as client from "@/api/client";
import Activity from "@/pages/Activity";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";
import type { ActivityEvent } from "@/api/types";

function event(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return {
    id: "e-1",
    timestamp: "2026-07-13T10:00:00",
    trace_id: "tr-1",
    event_type: "TASK_COMPLETED",
    status: "OK",
    actor: "AI_Agent",
    action_type: "ANALYSIS",
    input_context: null,
    output_content: "analysis finished",
    metadata: {},
    category: "tasks",
    ...overrides,
  };
}

function page(events: ActivityEvent[], total = events.length) {
  return {
    total,
    limit: 50,
    offset: 0,
    category: "all",
    query: "",
    events,
  };
}

describe("Activity page", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renders the feed with its category badge", async () => {
    vi.mocked(client.listActivity).mockResolvedValue(page([event()]));
    render(<Activity />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText("TASK_COMPLETED")).toBeInTheDocument(),
    );
    expect(screen.getByText("tasks")).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    vi.mocked(client.listActivity).mockResolvedValue(page([]));
    render(<Activity />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/no activity events/i)).toBeInTheDocument(),
    );
  });

  it("shows a loading indicator", () => {
    vi.mocked(client.listActivity).mockReturnValue(new Promise(() => {}));
    render(<Activity />, { wrapper: wrapperWith(createTestQueryClient()) });
    expect(screen.getByText(/loading activity/i)).toBeInTheDocument();
  });

  it("filters by category when a pill is clicked", async () => {
    vi.mocked(client.listActivity).mockResolvedValue(page([event()]));
    render(<Activity />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() => screen.getByText("TASK_COMPLETED"));

    await userEvent.click(screen.getByRole("button", { name: "Errors" }));
    await waitFor(() =>
      expect(client.listActivity).toHaveBeenLastCalledWith(
        expect.objectContaining({ category: "errors", offset: 0 }),
      ),
    );
  });

  it("passes a free-text query to the sidecar", async () => {
    vi.mocked(client.listActivity).mockResolvedValue(page([event()]));
    render(<Activity />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() => screen.getByText("TASK_COMPLETED"));

    await userEvent.type(screen.getByLabelText(/search activity/i), "crc");
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() =>
      expect(client.listActivity).toHaveBeenLastCalledWith(
        expect.objectContaining({ query: "crc" }),
      ),
    );
  });

  it("paginates with Next using offset", async () => {
    vi.mocked(client.listActivity).mockResolvedValue(page([event()], 120));
    render(<Activity />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() => screen.getByText("TASK_COMPLETED"));

    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() =>
      expect(client.listActivity).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 50 }),
      ),
    );
  });

  it("shows an error banner when the feed fails", async () => {
    vi.mocked(client.listActivity).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "feed dead" },
    });
    render(<Activity />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/feed dead/i),
    );
  });
});
