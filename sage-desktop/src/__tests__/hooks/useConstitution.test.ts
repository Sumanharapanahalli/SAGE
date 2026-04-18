import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  constitutionGet: vi.fn(),
  constitutionUpdate: vi.fn(),
  constitutionCheckAction: vi.fn(),
}));

import * as client from "@/api/client";
import {
  constitutionKey,
  useCheckAction,
  useConstitution,
  useUpdateConstitution,
} from "@/hooks/useConstitution";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("useConstitution", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns the full state from the sidecar", async () => {
    vi.mocked(client.constitutionGet).mockResolvedValue({
      data: { meta: { name: "demo", version: 1, last_updated: "", updated_by: "" } },
      stats: {
        is_empty: false,
        name: "demo",
        version: 1,
        principle_count: 0,
        constraint_count: 0,
        non_negotiable_count: 0,
        has_voice: false,
        has_decisions: false,
        has_knowledge: false,
        history_entries: 0,
      },
      preamble: "",
      history: [],
      errors: [],
    });
    const { result } = renderHook(() => useConstitution(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.stats.name).toBe("demo");
  });
});

describe("useUpdateConstitution", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invalidates the constitution query on success", async () => {
    vi.mocked(client.constitutionUpdate).mockResolvedValue({
      stats: {
        is_empty: false,
        name: "demo",
        version: 2,
        principle_count: 1,
        constraint_count: 0,
        non_negotiable_count: 0,
        has_voice: false,
        has_decisions: false,
        has_knowledge: false,
        history_entries: 1,
      },
      preamble: "",
      version: 2,
      path: "/tmp/demo/constitution.yaml",
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useUpdateConstitution(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ data: {} });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const keys = spy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(constitutionKey);
    expect(client.constitutionUpdate).toHaveBeenCalledWith({}, undefined);
  });

  it("passes changed_by through", async () => {
    vi.mocked(client.constitutionUpdate).mockResolvedValue({
      stats: {
        is_empty: false,
        name: "",
        version: 3,
        principle_count: 0,
        constraint_count: 0,
        non_negotiable_count: 0,
        has_voice: false,
        has_decisions: false,
        has_knowledge: false,
        history_entries: 0,
      },
      preamble: "",
      version: 3,
      path: "",
    });
    const { result } = renderHook(() => useUpdateConstitution(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ data: {}, changed_by: "alice" });
    await waitFor(() =>
      expect(client.constitutionUpdate).toHaveBeenCalledWith({}, "alice"),
    );
  });
});

describe("useCheckAction", () => {
  beforeEach(() => vi.clearAllMocks());

  it("forwards the description to the sidecar", async () => {
    vi.mocked(client.constitutionCheckAction).mockResolvedValue({
      allowed: false,
      violations: ["no prod"],
    });
    const { result } = renderHook(() => useCheckAction(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate("rm -rf /prod/");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.constitutionCheckAction).toHaveBeenCalledWith(
      "rm -rf /prod/",
    );
    expect(result.current.data?.allowed).toBe(false);
  });
});
