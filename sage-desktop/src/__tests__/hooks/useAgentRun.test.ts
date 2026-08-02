import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import {
  projectConfigKey,
  useAnalyzeJobDescription,
  useHireAgent,
  useProjectConfig,
  useRunAgent,
} from "@/hooks/useAgentRun";
import { approvalsKey } from "@/hooks/useApprovals";

import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

const PROPOSAL = {
  trace_id: "tr-hire-1",
  created_at: "2026-07-31T00:00:00Z",
  action_type: "agent_hire",
  risk_class: "STATEFUL",
  reversible: true,
  proposed_by: "desktop-operator",
  description: "Hire new agent role: 🤖 Level Balancer (level_balancer)",
  payload: { role_id: "level_balancer", solution: "four_in_a_line" },
  status: "pending",
  decided_by: null,
  decided_at: null,
  feedback: null,
  expires_at: null,
  required_role: null,
  approved_by: null,
  approver_role: null,
  approver_email: null,
} as never;

describe("useProjectConfig", () => {
  beforeEach(() => vi.resetAllMocks());

  it("returns the runnable roster from prompts.yaml", async () => {
    vi.mocked(client.getProjectConfig).mockResolvedValue({
      project: "four_in_a_line",
      agents: [
        {
          id: "game_designer",
          name: "Game Designer",
          description: "",
          icon: "🎲",
        },
      ],
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useProjectConfig(), {
      wrapper: wrapperWith(qc),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.agents[0].id).toBe("game_designer");
  });
});

describe("useRunAgent", () => {
  beforeEach(() => vi.resetAllMocks());

  it("returns the agent result AND the proposal it was persisted as", async () => {
    vi.mocked(client.runAgent).mockResolvedValue({
      result: { severity: "HIGH", summary: "looks risky" },
      proposal: { ...(PROPOSAL as object), action_type: "agent_run" } as never,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useRunAgent(), {
      wrapper: wrapperWith(qc),
    });

    result.current.mutate({ role_id: "game_designer", task: "review" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.runAgent).toHaveBeenCalledWith(
      "game_designer",
      "review",
      undefined,
    );
    expect(result.current.data?.proposal.action_type).toBe("agent_run");
  });

  it("refreshes the approvals inbox, since the run persisted a proposal", async () => {
    vi.mocked(client.runAgent).mockResolvedValue({
      result: {},
      proposal: PROPOSAL,
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useRunAgent(), {
      wrapper: wrapperWith(qc),
    });

    result.current.mutate({ role_id: "game_designer", task: "review" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalledWith({ queryKey: approvalsKey });
  });
});

describe("useHireAgent", () => {
  beforeEach(() => vi.resetAllMocks());

  it("resolves to a pending agent_hire proposal, not an applied role", async () => {
    vi.mocked(client.hireAgent).mockResolvedValue(PROPOSAL);
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useHireAgent(), {
      wrapper: wrapperWith(qc),
    });

    result.current.mutate({
      role_id: "level_balancer",
      name: "Level Balancer",
      system_prompt: "You tune difficulty curves.",
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.action_type).toBe("agent_hire");
    expect(result.current.data?.status).toBe("pending");
  });

  it("refreshes approvals but NOT the roster — the role is not live until approved", async () => {
    // Law 1: prompts.yaml is written by proposal_executor._execute_agent_hire
    // on approval. Invalidating the roster here would make the UI re-fetch and
    // imply the hire had already taken effect.
    vi.mocked(client.hireAgent).mockResolvedValue(PROPOSAL);
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useHireAgent(), {
      wrapper: wrapperWith(qc),
    });

    result.current.mutate({
      role_id: "level_balancer",
      name: "Level Balancer",
      system_prompt: "You tune difficulty curves.",
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(spy).toHaveBeenCalledWith({ queryKey: approvalsKey });
    expect(spy).not.toHaveBeenCalledWith({ queryKey: projectConfigKey });
  });
});

describe("useAnalyzeJobDescription", () => {
  beforeEach(() => vi.resetAllMocks());

  it("extracts a role draft without creating anything", async () => {
    vi.mocked(client.analyzeJobDescription).mockResolvedValue({
      role_key: "level_balancer",
      name: "Level Balancer",
      description: "Balances difficulty",
      system_prompt: "You tune difficulty curves.",
      // agent_factory prompts the LLM for {name, description} objects — NOT
      // the plain strings agentrun.hire accepts. See normalizeTaskTypes.
      task_types: [{ name: "BALANCE_REVIEW", description: "review balance" }],
    });
    const qc = createTestQueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useAnalyzeJobDescription(), {
      wrapper: wrapperWith(qc),
    });

    result.current.mutate({ jd_text: "We need someone to tune levels." });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // The framework returns `role_key`; hireAgent takes `role_id`. Pinning it
    // here so a caller wiring the two together sees the mismatch.
    expect(result.current.data?.role_key).toBe("level_balancer");
    expect(spy).not.toHaveBeenCalled();
  });
});
