import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
import Collective from "@/pages/Collective";

import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

const STATS_ONLINE = {
  learning_count: 1,
  help_request_count: 0,
  help_requests_closed: 0,
  topics: { uart: 1 },
  contributors: { medtech: 1 },
  git_available: true,
  repo_path: "/tmp/x",
};

const LEARNING = {
  id: "l1",
  author_agent: "analyst",
  author_solution: "medtech",
  topic: "uart",
  title: "UART recovery",
  content: "flush…",
  tags: [],
  confidence: 0.6,
  validation_count: 0,
  created_at: "",
  updated_at: "",
  source_task_id: "",
};

describe("Collective page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders header stats and learnings on the Learnings tab", async () => {
    vi.mocked(client.collectiveStats).mockResolvedValue(STATS_ONLINE);
    vi.mocked(client.collectiveListLearnings).mockResolvedValue({
      entries: [LEARNING],
      total: 1,
      limit: 50,
      offset: 0,
    });
    vi.mocked(client.collectiveListHelpRequests).mockResolvedValue({
      entries: [],
      count: 0,
    });
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <Collective />
      </Wrapper>,
    );
    await waitFor(() =>
      expect(screen.getByText("UART recovery")).toBeInTheDocument(),
    );
    expect(screen.getByText(/\/tmp\/x/)).toBeInTheDocument();
    expect(screen.getByText(/git: available/i)).toBeInTheDocument();
  });

  it("shows offline banner when git_available is false", async () => {
    vi.mocked(client.collectiveStats).mockResolvedValue({
      ...STATS_ONLINE,
      git_available: false,
    });
    vi.mocked(client.collectiveListLearnings).mockResolvedValue({
      entries: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    vi.mocked(client.collectiveListHelpRequests).mockResolvedValue({
      entries: [],
      count: 0,
    });
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <Collective />
      </Wrapper>,
    );
    await waitFor(() =>
      expect(screen.getByText(/git: offline/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /sync/i })).toBeDisabled();
  });

  it("switches to the Help Requests tab", async () => {
    vi.mocked(client.collectiveStats).mockResolvedValue(STATS_ONLINE);
    vi.mocked(client.collectiveListLearnings).mockResolvedValue({
      entries: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    vi.mocked(client.collectiveListHelpRequests).mockResolvedValue({
      entries: [
        {
          id: "hr-1",
          title: "I2C help",
          requester_agent: "dev",
          requester_solution: "auto",
          status: "open",
          urgency: "high",
          required_expertise: ["i2c"],
          context: "",
          created_at: "",
          claimed_by: null,
          responses: [],
          resolved_at: null,
        },
      ],
      count: 1,
    });
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <Collective />
      </Wrapper>,
    );
    fireEvent.click(screen.getByRole("button", { name: /help requests/i }));
    await waitFor(() => expect(screen.getByText("I2C help")).toBeInTheDocument());
  });
});
