import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  collectiveListLearnings: vi.fn(),
  collectiveSearchLearnings: vi.fn(),
  collectiveStats: vi.fn(),
  collectiveListHelpRequests: vi.fn(),
  collectivePublishLearning: vi.fn(),
  collectiveValidateLearning: vi.fn(),
  collectiveCreateHelpRequest: vi.fn(),
  collectiveClaimHelpRequest: vi.fn(),
  collectiveRespondToHelpRequest: vi.fn(),
  collectiveCloseHelpRequest: vi.fn(),
  collectiveSync: vi.fn(),
}));

import * as client from "@/api/client";
import {
  collectiveKeys,
  useCollectiveHelpList,
  useCollectiveList,
  useCollectiveSearch,
  useCollectiveStats,
  usePublishLearning,
  useValidateLearning,
} from "@/hooks/useCollective";

import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

const LEARNING = {
  id: "l1",
  author_agent: "analyst",
  author_solution: "medtech",
  topic: "uart",
  title: "UART recovery",
  content: "flush buffer…",
  tags: [],
  confidence: 0.6,
  validation_count: 0,
  created_at: "",
  updated_at: "",
  source_task_id: "",
};

describe("useCollective hooks", () => {
  beforeEach(() => vi.clearAllMocks());

  it("list query calls collectiveListLearnings and returns data", async () => {
    vi.mocked(client.collectiveListLearnings).mockResolvedValue({
      entries: [LEARNING],
      total: 1,
      limit: 50,
      offset: 0,
    });
    const wrapper = wrapperWith(createTestQueryClient());
    const { result } = renderHook(() => useCollectiveList({ limit: 50 }), {
      wrapper,
    });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.total).toBe(1);
    expect(client.collectiveListLearnings).toHaveBeenCalledWith({ limit: 50 });
  });

  it("search query is disabled when query is empty", () => {
    vi.mocked(client.collectiveSearchLearnings).mockResolvedValue({
      query: "",
      results: [],
      count: 0,
    });
    const wrapper = wrapperWith(createTestQueryClient());
    renderHook(() => useCollectiveSearch({ query: "" }), { wrapper });
    expect(client.collectiveSearchLearnings).not.toHaveBeenCalled();
  });

  it("stats query surfaces the backend flag", async () => {
    vi.mocked(client.collectiveStats).mockResolvedValue({
      learning_count: 2,
      help_request_count: 0,
      help_requests_closed: 0,
      topics: {},
      contributors: {},
      git_available: true,
      repo_path: "/tmp/x",
    });
    const wrapper = wrapperWith(createTestQueryClient());
    const { result } = renderHook(() => useCollectiveStats(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.git_available).toBe(true);
  });

  it("help list query passes status through", async () => {
    vi.mocked(client.collectiveListHelpRequests).mockResolvedValue({
      entries: [],
      count: 0,
    });
    const wrapper = wrapperWith(createTestQueryClient());
    renderHook(() => useCollectiveHelpList({ status: "closed" }), {
      wrapper,
    });
    await waitFor(() =>
      expect(client.collectiveListHelpRequests).toHaveBeenCalledWith({
        status: "closed",
      }),
    );
  });

  it("publish mutation invalidates the collective key", async () => {
    vi.mocked(client.collectivePublishLearning).mockResolvedValue({
      id: "l2",
      gated: false,
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const wrapper = wrapperWith(qc);
    const { result } = renderHook(() => usePublishLearning(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        author_agent: "analyst",
        author_solution: "medtech",
        topic: "uart",
        title: "T",
        content: "C",
      });
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: collectiveKeys.all });
  });

  it("validate mutation calls client with id and validator", async () => {
    vi.mocked(client.collectiveValidateLearning).mockResolvedValue({
      learning: { ...LEARNING, validation_count: 1 },
    });
    const qc = createTestQueryClient();
    const wrapper = wrapperWith(qc);
    const { result } = renderHook(() => useValidateLearning(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        id: "l1",
        validated_by: "qa@medtech",
      });
    });
    expect(client.collectiveValidateLearning).toHaveBeenCalledWith(
      "l1",
      "qa@medtech",
    );
  });
});
