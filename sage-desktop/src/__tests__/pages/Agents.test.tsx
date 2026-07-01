import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listAgents: vi.fn(),
  getAgent: vi.fn(),
  getAgentPerformance: vi.fn(),
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
