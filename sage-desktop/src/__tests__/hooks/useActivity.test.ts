import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import { useActivity } from "@/hooks/useActivity";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

const RESPONSE = {
  total: 1,
  limit: 50,
  offset: 0,
  category: "errors",
  query: "",
  events: [
    {
      id: "e1",
      timestamp: "2026-07-13T10:00:00",
      trace_id: "tr-1",
      event_type: "LLM_ERROR",
      status: "ERROR",
      actor: "AI_Agent",
      action_type: "GENERATE",
      input_context: null,
      output_content: "provider timeout",
      metadata: {},
      category: "errors" as const,
    },
  ],
};

describe("useActivity", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches the triage feed with the given filters", async () => {
    vi.mocked(client.listActivity).mockResolvedValue(RESPONSE);
    const { result } = renderHook(
      () => useActivity({ category: "errors", limit: 50, offset: 0 }),
      { wrapper: wrapperWith(createTestQueryClient()) },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.listActivity).toHaveBeenCalledWith({
      category: "errors",
      limit: 50,
      offset: 0,
    });
    expect(result.current.data?.events[0].category).toBe("errors");
  });

  it("surfaces a DesktopError", async () => {
    vi.mocked(client.listActivity).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "boom" },
    });
    const { result } = renderHook(() => useActivity(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.kind).toBe("SidecarDown");
  });
});
