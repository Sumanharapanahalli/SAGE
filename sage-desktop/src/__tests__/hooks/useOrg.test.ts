import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getOrg: vi.fn(),
  updateOrg: vi.fn(),
  reloadOrg: vi.fn(),
}));

import * as client from "@/api/client";
import { orgKey, useOrg, useReloadOrg, useUpdateOrg } from "@/hooks/useOrg";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

describe("useOrg", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns the enriched org state from the sidecar", async () => {
    vi.mocked(client.getOrg).mockResolvedValue({
      org: { name: "Acme", mission: "Ship things", core_values: ["Speed"] },
      routes: [{ source: "a", target: "b" }],
    });
    const { result } = renderHook(() => useOrg(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.org.name).toBe("Acme");
    expect(result.current.data?.routes).toEqual([{ source: "a", target: "b" }]);
  });
});

describe("useUpdateOrg", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invalidates the org query on success", async () => {
    vi.mocked(client.updateOrg).mockResolvedValue({
      status: "saved",
      org: { name: "Acme" },
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useUpdateOrg(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ name: "Acme" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const keys = spy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(orgKey);
    expect(client.updateOrg).toHaveBeenCalledWith({ name: "Acme" });
  });
});

describe("useReloadOrg", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invalidates the org query on success", async () => {
    vi.mocked(client.reloadOrg).mockResolvedValue({ status: "reloaded" });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useReloadOrg(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const keys = spy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(orgKey);
  });
});
