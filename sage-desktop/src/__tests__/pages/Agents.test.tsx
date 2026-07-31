import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// A full factory (no importOriginal), so every client function the page uses
// must be listed here or it arrives as undefined at call time.
vi.mock("@/api/client", () => ({
  listAgents: vi.fn(),
  getAgent: vi.fn(),
  getAgentPerformance: vi.fn(),
  getProjectConfig: vi.fn(),
  runAgent: vi.fn(),
  hireAgent: vi.fn(),
  analyzeJobDescription: vi.fn(),
}));

import * as client from "@/api/client";
import { Agents } from "@/pages/Agents";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";
import type { Agent, AgentPerformance } from "@/api/types";

const a1: Agent = {
  name: "analyst",
  kind: "core",
  description: "analyzes",
  system_prompt: "You are an analyst.",
  event_count: 1,
  last_active: null,
};

const perf: AgentPerformance = {
  role_key: "analyst",
  total_proposals: 3,
  approved: 2,
  rejected: 1,
  approval_rate: 66.7,
};

const PROPOSAL = {
  trace_id: "tr-1",
  created_at: "2026-07-31T00:00:00Z",
  action_type: "agent_hire",
  risk_class: "STATEFUL",
  reversible: true,
  proposed_by: "desktop-operator",
  description: "Hire new agent role: 🤖 Level Balancer (level_balancer)",
  payload: {},
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

/** The runnable roster comes from prompts.yaml via agentrun.get_project. */
const PROJECT_CONFIG = {
  project: "four_in_a_line",
  agents: [
    {
      id: "game_designer",
      name: "Game Designer",
      description: "designs",
      icon: "🎲",
    },
  ],
} as never;

async function openTab(
  user: ReturnType<typeof userEvent.setup>,
  name: RegExp,
) {
  await user.click(screen.getByRole("tab", { name }));
}

describe("Agents page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the roster", async () => {
    vi.mocked(client.listAgents).mockResolvedValue([a1]);
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/analyst/i)).toBeInTheDocument(),
    );
  });

  it("shows empty state when no agents", async () => {
    vi.mocked(client.listAgents).mockResolvedValue([]);
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/no agents/i)).toBeInTheDocument(),
    );
  });

  it("shows performance stats after selecting an agent", async () => {
    vi.mocked(client.listAgents).mockResolvedValue([a1]);
    vi.mocked(client.getAgentPerformance).mockResolvedValue(perf);
    const user = userEvent.setup();
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });

    await waitFor(() =>
      expect(screen.getByText(/analyst/i)).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /view performance/i }));

    await waitFor(() =>
      expect(client.getAgentPerformance).toHaveBeenCalledWith("analyst"),
    );
    await waitFor(() => expect(screen.getByText(/66\.7/)).toBeInTheDocument());
    expect(
      screen.getByText("Total proposals").nextElementSibling,
    ).toHaveTextContent("3");
    expect(screen.getByText("Approved").nextElementSibling).toHaveTextContent(
      "2",
    );
    expect(screen.getByText("Rejected").nextElementSibling).toHaveTextContent(
      "1",
    );
  });

  it("shows 'No history yet' when approval_rate is null", async () => {
    vi.mocked(client.listAgents).mockResolvedValue([a1]);
    vi.mocked(client.getAgentPerformance).mockResolvedValue({
      role_key: "analyst",
      total_proposals: 0,
      approved: 0,
      rejected: 0,
      approval_rate: null,
    });
    const user = userEvent.setup();
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });

    await waitFor(() =>
      expect(screen.getByText(/analyst/i)).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /view performance/i }));

    await waitFor(() =>
      expect(screen.getByText(/no history yet/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/nan%/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/null%/i)).not.toBeInTheDocument();
  });
});

// ── Run tab ────────────────────────────────────────────────────────────────

describe("Agents page — Run", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.listAgents).mockResolvedValue([a1]);
    vi.mocked(client.getProjectConfig).mockResolvedValue(PROJECT_CONFIG);
  });

  it("offers the RUNNABLE roles from prompts.yaml, not the core roster", async () => {
    // agents.list is an audit-annotated view that also includes the four core
    // roles — UniversalAgent.run cannot dispatch to those, so offering them
    // here would produce a guaranteed "unknown role" error.
    const user = userEvent.setup();
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await openTab(user, /run/i);

    await waitFor(() =>
      expect(screen.getByRole("option", { name: /game designer/i })).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("option", { name: /^analyst$/i }),
    ).not.toBeInTheDocument();
  });

  it("runs the selected role and reports that it needs approval", async () => {
    vi.mocked(client.runAgent).mockResolvedValue({
      result: { severity: "HIGH", summary: "looks risky" },
      proposal: { ...(PROPOSAL as object), action_type: "agent_run" } as never,
    });
    const user = userEvent.setup();
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await openTab(user, /run/i);

    await waitFor(() =>
      expect(screen.getByRole("option", { name: /game designer/i })).toBeInTheDocument(),
    );
    await user.type(screen.getByLabelText(/task/i), "review the board");
    await user.click(screen.getByRole("button", { name: /run agent/i }));

    await waitFor(() =>
      expect(client.runAgent).toHaveBeenCalledWith(
        "game_designer",
        "review the board",
        "",
      ),
    );
    // The run is persisted as a proposal — the page must not imply it is done.
    await waitFor(() =>
      expect(screen.getByText(/awaiting human approval/i)).toBeInTheDocument(),
    );
  });

  it("surfaces a failed run", async () => {
    vi.mocked(client.runAgent).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "unknown role" },
    });
    const user = userEvent.setup();
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await openTab(user, /run/i);

    await waitFor(() =>
      expect(screen.getByRole("option", { name: /game designer/i })).toBeInTheDocument(),
    );
    await user.type(screen.getByLabelText(/task/i), "x");
    await user.click(screen.getByRole("button", { name: /run agent/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/unknown role/i),
    );
  });
});

// ── Hire tab ───────────────────────────────────────────────────────────────

describe("Agents page — Hire", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.listAgents).mockResolvedValue([a1]);
    vi.mocked(client.getProjectConfig).mockResolvedValue(PROJECT_CONFIG);
  });

  it("fills the draft from a job description, mapping role_key to role_id", async () => {
    vi.mocked(client.analyzeJobDescription).mockResolvedValue({
      role_key: "level_balancer",
      name: "Level Balancer",
      description: "Balances difficulty",
      system_prompt: "You tune difficulty curves.",
      // agent_factory prompts the LLM for OBJECTS, not strings.
      task_types: [
        { name: "BALANCE_REVIEW", description: "review balance" },
        { name: "DIFFICULTY_AUDIT", description: "audit difficulty" },
      ],
    });
    const user = userEvent.setup();
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await openTab(user, /hire/i);

    await user.type(
      screen.getByLabelText(/job description/i),
      "We need someone to tune levels.",
    );
    await user.click(screen.getByRole("button", { name: /analyze/i }));

    await waitFor(() =>
      expect(screen.getByLabelText(/role id/i)).toHaveValue("level_balancer"),
    );
    expect(screen.getByLabelText(/^name/i)).toHaveValue("Level Balancer");
    // Objects flattened to names — a bare `t.name` on a string array would
    // have produced "undefined, undefined" here.
    expect(screen.getByLabelText(/task types/i)).toHaveValue(
      "BALANCE_REVIEW, DIFFICULTY_AUDIT",
    );
  });

  it("proposes the hire with task_types as plain strings", async () => {
    // The regression that matters: agentrun.hire rejects the whole payload
    // with "'task_types' must be a list of strings" if the drafted objects
    // are passed through unmapped.
    vi.mocked(client.analyzeJobDescription).mockResolvedValue({
      role_key: "level_balancer",
      name: "Level Balancer",
      description: "Balances difficulty",
      system_prompt: "You tune difficulty curves.",
      task_types: [{ name: "BALANCE_REVIEW" }],
    });
    vi.mocked(client.hireAgent).mockResolvedValue(PROPOSAL);
    const user = userEvent.setup();
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await openTab(user, /hire/i);

    await user.type(screen.getByLabelText(/job description/i), "tune levels");
    await user.click(screen.getByRole("button", { name: /analyze/i }));
    await waitFor(() =>
      expect(screen.getByLabelText(/role id/i)).toHaveValue("level_balancer"),
    );
    await user.click(screen.getByRole("button", { name: /propose hire/i }));

    await waitFor(() =>
      expect(client.hireAgent).toHaveBeenCalledWith(
        expect.objectContaining({
          role_id: "level_balancer",
          name: "Level Balancer",
          system_prompt: "You tune difficulty curves.",
          task_types: ["BALANCE_REVIEW"],
        }),
      ),
    );
  });

  it("says the role is awaiting approval, never that it was created", async () => {
    // Law 1: prompts.yaml is written by proposal_executor._execute_agent_hire
    // on approval. Telling the operator the role exists would be a lie.
    vi.mocked(client.hireAgent).mockResolvedValue(PROPOSAL);
    const user = userEvent.setup();
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await openTab(user, /hire/i);

    await user.type(screen.getByLabelText(/role id/i), "level_balancer");
    await user.type(screen.getByLabelText(/^name/i), "Level Balancer");
    await user.type(
      screen.getByLabelText(/system prompt/i),
      "You tune difficulty curves.",
    );
    await user.click(screen.getByRole("button", { name: /propose hire/i }));

    await waitFor(() =>
      expect(screen.getByText(/awaiting human approval/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/role created/i)).not.toBeInTheDocument();
  });

  it("does not hire without a role id, name and system prompt", async () => {
    const user = userEvent.setup();
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await openTab(user, /hire/i);

    expect(screen.getByRole("button", { name: /propose hire/i })).toBeDisabled();
    expect(client.hireAgent).not.toHaveBeenCalled();
  });
});
