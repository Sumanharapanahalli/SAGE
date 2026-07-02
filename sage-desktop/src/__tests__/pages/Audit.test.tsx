import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listAuditEvents: vi.fn(),
  getAuditByTrace: vi.fn(),
  auditStats: vi.fn(),
}));

import * as client from "@/api/client";
import { Audit } from "@/pages/Audit";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";
import type { AuditEvent } from "@/api/types";

function event(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: "e-1",
    timestamp: "2026-04-16T10:00:00Z",
    trace_id: "t-1",
    event_type: "analysis",
    status: null,
    actor: "analyst",
    action_type: "yaml_edit",
    input_context: null,
    output_content: null,
    metadata: {},
    approved_by: null,
    approver_role: null,
    approver_email: null,
    approver_provider: null,
    ...overrides,
  };
}

describe("Audit page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.auditStats).mockResolvedValue({
      total: 3,
      by_action_type: { yaml_edit: 2, approved: 1 },
    });
  });

  it("renders table rows", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 1,
      limit: 50,
      offset: 0,
      events: [event()],
    });
    render(<Audit />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(
        screen.getByRole("cell", { name: "yaml_edit" }),
      ).toBeInTheDocument(),
    );
  });

  it("shows empty state", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 0,
      limit: 50,
      offset: 0,
      events: [],
    });
    render(<Audit />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/no audit events/i)).toBeInTheDocument(),
    );
  });

  it("populates the action-type filter from audit stats", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 1,
      limit: 50,
      offset: 0,
      events: [event()],
    });
    render(<Audit />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(
        screen.getByRole("option", { name: "yaml_edit" }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("option", { name: "approved" })).toBeInTheDocument();
  });

  it("drills into a trace when its id is clicked", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 1,
      limit: 50,
      offset: 0,
      events: [event({ trace_id: "trace-xyz" })],
    });
    vi.mocked(client.getAuditByTrace).mockResolvedValue({
      trace_id: "trace-xyz",
      events: [
        event({ id: "s1", trace_id: "trace-xyz", action_type: "analysis" }),
        event({
          id: "s2",
          trace_id: "trace-xyz",
          action_type: "approved",
          output_content: "looks good",
        }),
      ],
    });
    render(<Audit />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() => screen.getByRole("button", { name: "trace-xyz" }));
    await userEvent.click(screen.getByRole("button", { name: "trace-xyz" }));

    await waitFor(() =>
      expect(client.getAuditByTrace).toHaveBeenCalledWith("trace-xyz"),
    );
    expect(screen.getByText(/looks good/)).toBeInTheDocument();
  });

  it("paginates with Next using offset", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 120,
      limit: 50,
      offset: 0,
      events: [event()],
    });
    render(<Audit />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() => screen.getByRole("cell", { name: "yaml_edit" }));

    await userEvent.click(screen.getByRole("button", { name: /next/i }));
    await waitFor(() =>
      expect(client.listAuditEvents).toHaveBeenLastCalledWith(
        expect.objectContaining({ offset: 50 }),
      ),
    );
  });

  it("shows an error banner when the list query fails", async () => {
    vi.mocked(client.listAuditEvents).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "dead" },
    });
    render(<Audit />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i),
    );
  });
});
