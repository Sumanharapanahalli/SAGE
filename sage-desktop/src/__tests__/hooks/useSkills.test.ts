import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import {
  useSkills,
  useSetSkillVisibility,
  useReloadSkills,
  useMcpTools,
} from "@/hooks/useSkills";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

const SKILL = {
  name: "tdd",
  version: "1.0.0",
  visibility: "public",
  roles: ["developer"],
  runner: "software",
  description: "Test-driven development",
  tools: [],
  prompt: "",
  acceptance_criteria: [],
  certifications: [],
  engines: [],
  tags: [],
};

const STATS = {
  total: 1,
  active: 1,
  public: 1,
  private: 0,
  disabled: 0,
  roles_covered: 1,
  runners_covered: 1,
  loaded_dirs: ["skills/public"],
};

describe("useSkills", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists skills with stats", async () => {
    vi.mocked(client.listSkills).mockResolvedValue({
      skills: [SKILL],
      stats: STATS,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useSkills(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.skills[0].name).toBe("tdd");
    expect(client.listSkills).toHaveBeenCalledWith(undefined);
  });

  it("passes include_disabled through to the client", async () => {
    vi.mocked(client.listSkills).mockResolvedValue({
      skills: [SKILL],
      stats: STATS,
    });
    const qc = createTestQueryClient();
    renderHook(() => useSkills(true), { wrapper: wrapperWith(qc) });
    await waitFor(() =>
      expect(client.listSkills).toHaveBeenCalledWith(true),
    );
  });
});

describe("useSetSkillVisibility", () => {
  beforeEach(() => vi.resetAllMocks());

  it("sets visibility and invalidates the skills query", async () => {
    vi.mocked(client.setSkillVisibility).mockResolvedValue({
      status: "updated",
      name: "tdd",
      visibility: "private",
    });
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useSetSkillVisibility(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ name: "tdd", visibility: "private" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.setSkillVisibility).toHaveBeenCalledWith("tdd", "private");
    expect(invalidateSpy).toHaveBeenCalled();
  });
});

describe("useReloadSkills", () => {
  beforeEach(() => vi.resetAllMocks());

  it("reloads skills and invalidates the skills query", async () => {
    vi.mocked(client.reloadSkills).mockResolvedValue({
      status: "reloaded",
      skills_loaded: 21,
      stats: STATS,
    });
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useReloadSkills(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.skills_loaded).toBe(21);
    expect(invalidateSpy).toHaveBeenCalled();
  });
});

describe("useMcpTools", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists mcp tools", async () => {
    vi.mocked(client.listMcpTools).mockResolvedValue({
      tools: [{ name: "flash_firmware", description: "Flash firmware", server: "firmware" }],
      count: 1,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useMcpTools(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.tools[0].name).toBe("flash_firmware");
  });
});
