import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  checkUpdate: vi.fn(),
  installUpdate: vi.fn(),
}));

import * as client from "@/api/client";
import { useInstallUpdate, useUpdateCheck } from "@/hooks/useUpdate";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("useUpdateCheck", () => {
  beforeEach(() => vi.clearAllMocks());

  it("does not fetch while disabled", () => {
    const { result } = renderHook(() => useUpdateCheck(false), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.checkUpdate).not.toHaveBeenCalled();
  });

  it("returns UpToDate status when enabled", async () => {
    vi.mocked(client.checkUpdate).mockResolvedValue({
      kind: "UpToDate",
      current_version: "0.1.0",
    });
    const { result } = renderHook(() => useUpdateCheck(true), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      kind: "UpToDate",
      current_version: "0.1.0",
    });
  });

  it("surfaces Available payload", async () => {
    vi.mocked(client.checkUpdate).mockResolvedValue({
      kind: "Available",
      current_version: "0.1.0",
      new_version: "0.2.0",
      notes: "bug fixes",
    });
    const { result } = renderHook(() => useUpdateCheck(true), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({
      kind: "Available",
      new_version: "0.2.0",
    });
  });
});

describe("useInstallUpdate", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invokes install_update command", async () => {
    vi.mocked(client.installUpdate).mockResolvedValue(undefined);
    const { result } = renderHook(() => useInstallUpdate(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await act(async () => {
      await result.current.mutateAsync();
    });
    expect(client.installUpdate).toHaveBeenCalledOnce();
  });
});
