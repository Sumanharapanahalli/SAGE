import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listAgents: vi.fn(),
  getAgent: vi.fn(),
  getAgentPerformance: vi.fn(),
}));

import * as client from "@/api/client";
import { useAgent, useAgentPerformance, useAgents } from "@/hooks/useAgents";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";
import type { Agent, AgentPerformance } from "@/api/types";

const sample: Agent = {
  name: "analyst",
  kind: "core",
  description: "analyzes signals",
  system_prompt: "You are an analyst.",
  event_count: 3,
  last_active: "2026-04-16T10:00:00Z",
};

const perf: AgentPerformance = {
  role_key: "analyst",
  total_proposals: 3,
  approved: 2,
  rejected: 1,
  approval_rate: 66.7,
};

describe("useAgents", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches the agent roster", async () => {
    vi.mocked(client.listAgents).mockResolvedValue([sample]);
    const { result } = renderHook(() => useAgents(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([sample]);
  });
});

describe("useAgent", () => {
  beforeEach(() => vi.clearAllMocks());

  it("is idle for empty name", () => {
    const { result } = renderHook(() => useAgent(""), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.getAgent).not.toHaveBeenCalled();
  });

  it("fetches an agent by name", async () => {
    vi.mocked(client.getAgent).mockResolvedValue(sample);
    const { result } = renderHook(() => useAgent("analyst"), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getAgent).toHaveBeenCalledWith("analyst");
  });
});

describe("useAgentPerformance", () => {
  beforeEach(() => vi.clearAllMocks());

  it("is idle for empty role_key", () => {
    const { result } = renderHook(() => useAgentPerformance(""), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.getAgentPerformance).not.toHaveBeenCalled();
  });

  it("is idle when enabled is explicitly false", () => {
    const { result } = renderHook(
      () => useAgentPerformance("analyst", false),
      { wrapper: wrapperWith(createTestQueryClient()) },
    );
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.getAgentPerformance).not.toHaveBeenCalled();
  });

  it("fetches performance stats by role_key", async () => {
    vi.mocked(client.getAgentPerformance).mockResolvedValue(perf);
    const { result } = renderHook(() => useAgentPerformance("analyst"), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getAgentPerformance).toHaveBeenCalledWith("analyst");
    expect(result.current.data).toEqual(perf);
  });
});
