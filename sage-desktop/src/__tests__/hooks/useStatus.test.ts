import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getStatus: vi.fn(),
  handshake: vi.fn(),
}));

import * as client from "@/api/client";
import { useHandshake, useStatus } from "@/hooks/useStatus";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("useStatus", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches status", async () => {
    vi.mocked(client.getStatus).mockResolvedValue({
      health: "ok",
      sidecar_version: "0.1.0",
      project: null,
      llm: null,
      pending_approvals: 0,
    });
    const { result } = renderHook(() => useStatus(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.health).toBe("ok");
  });
});

describe("useHandshake", () => {
  beforeEach(() => vi.clearAllMocks());

  it("performs handshake", async () => {
    vi.mocked(client.handshake).mockResolvedValue({
      sidecar_version: "0.1.0",
      sage_version: "dev",
      solution_name: "none",
      solution_path: "",
      warnings: [],
    });
    const { result } = renderHook(() => useHandshake(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.sage_version).toBe("dev");
  });
});
