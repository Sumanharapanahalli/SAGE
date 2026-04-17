import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  onboardingGenerate: vi.fn(),
}));

import * as client from "@/api/client";
import { useOnboardingGenerate } from "@/hooks/useOnboarding";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("useOnboardingGenerate", () => {
  beforeEach(() => vi.clearAllMocks());

  it("passes params through and invalidates solutions on success", async () => {
    vi.mocked(client.onboardingGenerate).mockResolvedValue({
      solution_name: "yoga",
      path: "/abs/yoga",
      status: "created",
      files: { "project.yaml": "x" },
      suggested_routes: [],
      message: "ok",
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useOnboardingGenerate(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({
      description: "x".repeat(30),
      solution_name: "yoga",
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.onboardingGenerate).toHaveBeenCalledWith(
      expect.objectContaining({ solution_name: "yoga" }),
    );
    expect(spy).toHaveBeenCalled();
  });

  it("surfaces InvalidParams as a typed error", async () => {
    vi.mocked(client.onboardingGenerate).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "bad name" },
    });
    const { result } = renderHook(() => useOnboardingGenerate(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({
      description: "x".repeat(30),
      solution_name: "Bad Name",
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.kind).toBe("InvalidParams");
  });

  it("surfaces SidecarDown when LLM is unavailable", async () => {
    vi.mocked(client.onboardingGenerate).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "LLM unavailable" },
    });
    const { result } = renderHook(() => useOnboardingGenerate(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({
      description: "x".repeat(30),
      solution_name: "yoga",
    });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.kind).toBe("SidecarDown");
  });
});
