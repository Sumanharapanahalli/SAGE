import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listAgents: vi.fn(),
  getAgent: vi.fn(),
}));

import * as client from "@/api/client";
import { useAgent, useAgents } from "@/hooks/useAgents";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";
import type { Agent } from "@/api/types";

const sample: Agent = {
  name: "analyst",
  kind: "core",
  description: "analyzes signals",
  system_prompt: "You are an analyst.",
  event_count: 3,
  last_active: "2026-04-16T10:00:00Z",
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
