import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listAuditEvents: vi.fn(),
  getAuditByTrace: vi.fn(),
  auditStats: vi.fn(),
}));

import * as client from "@/api/client";
import {
  useAuditByTrace,
  useAuditEvents,
  useAuditStats,
} from "@/hooks/useAudit";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

const sampleEvent = {
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
};

describe("useAuditEvents", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches events with default params", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 1,
      limit: 50,
      offset: 0,
      events: [sampleEvent],
    });
    const { result } = renderHook(() => useAuditEvents(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.listAuditEvents).toHaveBeenCalledWith({});
    expect(result.current.data?.total).toBe(1);
  });

  it("passes filters through", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 0,
      limit: 10,
      offset: 0,
      events: [],
    });
    const { result } = renderHook(
      () => useAuditEvents({ action_type: "yaml_edit", limit: 10 }),
      { wrapper: wrapperWith(createTestQueryClient()) },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.listAuditEvents).toHaveBeenCalledWith({
      action_type: "yaml_edit",
      limit: 10,
    });
  });
});

describe("useAuditByTrace", () => {
  beforeEach(() => vi.clearAllMocks());

  it("is disabled for empty trace_id", () => {
    const { result } = renderHook(() => useAuditByTrace(""), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.getAuditByTrace).not.toHaveBeenCalled();
  });

  it("fetches when trace_id is set", async () => {
    vi.mocked(client.getAuditByTrace).mockResolvedValue({
      trace_id: "t-1",
      events: [sampleEvent],
    });
    const { result } = renderHook(() => useAuditByTrace("t-1"), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getAuditByTrace).toHaveBeenCalledWith("t-1");
  });
});

describe("useAuditStats", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches stats", async () => {
    vi.mocked(client.auditStats).mockResolvedValue({
      total: 42,
      by_action_type: { yaml_edit: 10, analysis: 32 },
    });
    const { result } = renderHook(() => useAuditStats(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total).toBe(42);
  });
});
