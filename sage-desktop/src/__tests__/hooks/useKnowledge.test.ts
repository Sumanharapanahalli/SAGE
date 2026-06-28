import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  knowledgeList: vi.fn(),
  knowledgeSearch: vi.fn(),
  knowledgeStats: vi.fn(),
  knowledgeAdd: vi.fn(),
  knowledgeDelete: vi.fn(),
}));

import * as client from "@/api/client";
import {
  knowledgeKeys,
  useAddKnowledge,
  useDeleteKnowledge,
  useKnowledgeList,
  useKnowledgeSearch,
  useKnowledgeStats,
} from "@/hooks/useKnowledge";

import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

describe("useKnowledgeList", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches a slice with limit and offset", async () => {
    vi.mocked(client.knowledgeList).mockResolvedValue({
      entries: [{ id: "a", text: "hello", metadata: {} }],
      total: 1,
      limit: 50,
      offset: 0,
    });
    const { result } = renderHook(() => useKnowledgeList(50, 0), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.knowledgeList).toHaveBeenCalledWith({ limit: 50, offset: 0 });
    expect(result.current.data?.total).toBe(1);
  });
});

describe("useKnowledgeSearch", () => {
  beforeEach(() => vi.clearAllMocks());

  it("is disabled for an empty query", () => {
    const { result } = renderHook(() => useKnowledgeSearch("", 10), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.knowledgeSearch).not.toHaveBeenCalled();
  });

  it("forwards query and top_k", async () => {
    vi.mocked(client.knowledgeSearch).mockResolvedValue({
      query: "vector",
      results: [{ text: "hit" }],
      count: 1,
    });
    const { result } = renderHook(() => useKnowledgeSearch("vector", 5), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.knowledgeSearch).toHaveBeenCalledWith("vector", 5);
  });
});

describe("useKnowledgeStats", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns backend + collection metadata", async () => {
    vi.mocked(client.knowledgeStats).mockResolvedValue({
      total: 3,
      collection: "demo_knowledge",
      backend: "full",
      solution: "demo",
    });
    const { result } = renderHook(() => useKnowledgeStats(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.backend).toBe("full");
  });
});

describe("useAddKnowledge", () => {
  beforeEach(() => vi.clearAllMocks());

  it("invalidates knowledge queries on success", async () => {
    vi.mocked(client.knowledgeAdd).mockResolvedValue({
      id: "uuid-1",
      text: "hi",
      metadata: {},
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useAddKnowledge(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ text: "hi" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.knowledgeAdd).toHaveBeenCalledWith("hi", undefined);
    const keys = spy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(knowledgeKeys.all);
  });
});

describe("useDeleteKnowledge", () => {
  beforeEach(() => vi.clearAllMocks());

  it("forwards id and invalidates on success", async () => {
    vi.mocked(client.knowledgeDelete).mockResolvedValue({
      id: "uuid-1",
      deleted: true,
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useDeleteKnowledge(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate("uuid-1");
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.knowledgeDelete).toHaveBeenCalledWith("uuid-1");
    const keys = spy.mock.calls.map((c) => c[0]?.queryKey);
    expect(keys).toContainEqual(knowledgeKeys.all);
  });
});
