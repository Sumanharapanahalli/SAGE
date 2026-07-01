import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import {
  useResumeWorkflow,
  useRunWorkflow,
  useWorkflowList,
  useWorkflowStatus,
} from "@/hooks/useWorkflows";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useWorkflowList", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists available workflows", async () => {
    vi.mocked(client.listWorkflows).mockResolvedValue({
      workflows: [{ name: "analysis_workflow" }],
      count: 1,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useWorkflowList(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.workflows[0].name).toBe("analysis_workflow");
  });
});

describe("useRunWorkflow", () => {
  beforeEach(() => vi.resetAllMocks());

  it("starts a workflow run with the given initial state", async () => {
    vi.mocked(client.runWorkflow).mockResolvedValue({
      run_id: "r1",
      status: "completed",
      workflow_name: "analysis_workflow",
      result: { ok: true },
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useRunWorkflow(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({
      workflow_name: "analysis_workflow",
      state: { task: "x" },
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.runWorkflow).toHaveBeenCalledWith("analysis_workflow", {
      task: "x",
    });
    expect(result.current.data?.run_id).toBe("r1");
  });
});

describe("useResumeWorkflow", () => {
  beforeEach(() => vi.resetAllMocks());

  it("resumes a run awaiting approval with feedback", async () => {
    vi.mocked(client.resumeWorkflow).mockResolvedValue({
      run_id: "r1",
      status: "completed",
      workflow_name: "analysis_workflow",
      result: { ok: true },
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useResumeWorkflow(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ run_id: "r1", feedback: { approved: true } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.resumeWorkflow).toHaveBeenCalledWith("r1", {
      approved: true,
    });
  });
});

describe("useWorkflowStatus", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches status for the given run_id", async () => {
    vi.mocked(client.getWorkflowStatus).mockResolvedValue({
      run_id: "r1",
      workflow_name: "analysis_workflow",
      status: "completed",
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useWorkflowStatus("r1"), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getWorkflowStatus).toHaveBeenCalledWith("r1");
  });

  it("does not fetch when run_id is empty", () => {
    const qc = createTestQueryClient();
    renderHook(() => useWorkflowStatus(""), {
      wrapper: wrapperWith(qc),
    });
    expect(client.getWorkflowStatus).not.toHaveBeenCalled();
  });

  it("does not fetch when enabled is false, even with a non-empty run_id", () => {
    const qc = createTestQueryClient();
    renderHook(() => useWorkflowStatus("r1", false), {
      wrapper: wrapperWith(qc),
    });
    expect(client.getWorkflowStatus).not.toHaveBeenCalled();
  });
});
