import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  telemetryGetStatus: vi.fn(),
  telemetrySetEnabled: vi.fn(),
  telemetryFlush: vi.fn(),
}));

import * as client from "@/api/client";
import {
  useFlushTelemetry,
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

describe("useFlushTelemetry", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns the sidecar's sent-count on success", async () => {
    vi.mocked(client.telemetryFlush).mockResolvedValue({
      sent: 3,
      reason: "ok",
    });
    const { result } = renderHook(() => useFlushTelemetry(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    let returned: { sent: number; reason: string } | undefined;
    await act(async () => {
      returned = await result.current.mutateAsync();
    });
    expect(client.telemetryFlush).toHaveBeenCalledOnce();
    expect(returned).toEqual({ sent: 3, reason: "ok" });
  });

  it("surfaces opt-out reason without throwing", async () => {
    vi.mocked(client.telemetryFlush).mockResolvedValue({
      sent: 0,
      reason: "opted_out",
    });
    const { result } = renderHook(() => useFlushTelemetry(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    let returned: { sent: number; reason: string } | undefined;
    await act(async () => {
      returned = await result.current.mutateAsync();
    });
    expect(returned?.reason).toBe("opted_out");
  });
});
