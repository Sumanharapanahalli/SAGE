import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  telemetryGetStatus: vi.fn(),
  telemetrySetEnabled: vi.fn(),
}));

import * as client from "@/api/client";
import {
  useSetTelemetryEnabled,
  useTelemetryStatus,
} from "@/hooks/useTelemetry";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("useTelemetryStatus", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns disabled-by-default status", async () => {
    vi.mocked(client.telemetryGetStatus).mockResolvedValue({
      enabled: false,
      anon_id: null,
      allowed_events: ["approval.decided"],
      allowed_fields: ["event", "status"],
    });
    const { result } = renderHook(() => useTelemetryStatus(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.enabled).toBe(false);
  });
});

describe("useSetTelemetryEnabled", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invokes telemetry_set_enabled with the boolean argument", async () => {
    vi.mocked(client.telemetrySetEnabled).mockResolvedValue({
      enabled: true,
      anon_id: "abc",
      allowed_events: [],
      allowed_fields: [],
    });
    const { result } = renderHook(() => useSetTelemetryEnabled(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await act(async () => {
      await result.current.mutateAsync(true);
    });
    expect(client.telemetrySetEnabled).toHaveBeenCalledWith(true);
  });
});
