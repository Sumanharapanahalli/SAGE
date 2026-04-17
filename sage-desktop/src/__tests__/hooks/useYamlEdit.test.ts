import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  readYaml: vi.fn(),
  writeYaml: vi.fn(),
}));

import * as client from "@/api/client";
import { useReadYaml, useWriteYaml } from "@/hooks/useYamlEdit";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("useReadYaml", () => {
  beforeEach(() => vi.clearAllMocks());

  it("skips the fetch when file is undefined", () => {
    const { result } = renderHook(() => useReadYaml(undefined), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.readYaml).not.toHaveBeenCalled();
  });

  it("fetches the selected file", async () => {
    vi.mocked(client.readYaml).mockResolvedValue({
      file: "project",
      solution: "demo",
      content: "name: demo\n",
      path: "/abs/project.yaml",
    });
    const { result } = renderHook(() => useReadYaml("project"), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.readYaml).toHaveBeenCalledWith("project");
    expect(result.current.data?.content).toContain("name: demo");
  });
});

describe("useWriteYaml", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls writeYaml and invalidates the corresponding read query", async () => {
    vi.mocked(client.writeYaml).mockResolvedValue({
      file: "prompts",
      solution: "demo",
      path: "/abs/prompts.yaml",
      bytes: 42,
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useWriteYaml(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ file: "prompts", content: "agents: []\n" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.writeYaml).toHaveBeenCalledWith("prompts", "agents: []\n");
    expect(spy).toHaveBeenCalledWith({
      queryKey: ["yaml", "prompts"],
    });
  });

  it("surfaces InvalidParams on bad YAML", async () => {
    vi.mocked(client.writeYaml).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "Invalid YAML: …" },
    });
    const { result } = renderHook(() => useWriteYaml(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ file: "project", content: "{: bad" });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.kind).toBe("InvalidParams");
  });
});
