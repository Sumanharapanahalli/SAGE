import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import { useLlmInfo, useSwitchLlm } from "@/hooks/useLlm";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useLlmInfo", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches current provider info", async () => {
    vi.mocked(client.getLlmInfo).mockResolvedValue({
      provider_name: "GeminiCLIProvider",
      model: "gemini-2.0-flash-001",
      available_providers: ["gemini", "claude-code"],
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useLlmInfo(), { wrapper: wrapperWith(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.provider_name).toBe("GeminiCLIProvider");
  });
});

describe("useSwitchLlm", () => {
  beforeEach(() => vi.resetAllMocks());

  it("invokes switchLlm and invalidates llm cache", async () => {
    vi.mocked(client.switchLlm).mockResolvedValue({
      provider: "ollama",
      provider_name: "OllamaProvider",
      saved_as_default: true,
    });
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useSwitchLlm(), { wrapper: wrapperWith(qc) });
    result.current.mutate({ provider: "ollama", model: "llama3.2", save_as_default: true });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["llm"] });
  });
});
