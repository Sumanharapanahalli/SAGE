import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import MergeRequests from "@/pages/MergeRequests";

import { createTestQueryClient } from "../helpers/queryWrapper";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    mrConfig: vi.fn(),
    listOpenMrs: vi.fn(),
    reviewMr: vi.fn(),
    proposeMr: vi.fn(),
    commentOnMr: vi.fn(),
  };
});

const CONFIGURED = {
  configured: true,
  gitlab_url: "https://gitlab.example.com",
  has_token: true,
  default_project_id: "12",
  message: "",
};

const PROPOSAL = {
  trace_id: "tr-1",
  created_at: "2026-07-31T00:00:00Z",
  action_type: "mr_create",
  risk_class: "EXTERNAL",
  reversible: false,
  proposed_by: "DeveloperAgent",
  description: "Create GitLab MR from issue #45: Fix the thing",
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

function renderPage() {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MergeRequests />
    </QueryClientProvider>,
  );
}

async function loadProject(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/gitlab project id/i), "12");
  await user.click(screen.getByRole("button", { name: /load open mrs/i }));
  await waitFor(() => expect(client.listOpenMrs).toHaveBeenCalledWith(12));
}

describe("MergeRequests page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.mrConfig).mockResolvedValue(CONFIGURED);
    vi.mocked(client.listOpenMrs).mockResolvedValue({
      merge_requests: [{ iid: 7, title: "Add thing" }],
    });
  });

  it("shows a setup prompt when GitLab is unconfigured", async () => {
    vi.mocked(client.mrConfig).mockResolvedValue({
      ...CONFIGURED,
      configured: false,
      has_token: false,
      message: "Set GITLAB_URL and GITLAB_TOKEN to enable GitLab.",
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/not configured/i),
    );
    // No point offering operations that cannot possibly work.
    expect(
      screen.queryByRole("button", { name: /load open mrs/i }),
    ).not.toBeInTheDocument();
  });

  it("does not fetch merge requests until a project is chosen", async () => {
    renderPage();
    await waitFor(() => expect(client.mrConfig).toHaveBeenCalled());
    expect(client.listOpenMrs).not.toHaveBeenCalled();
  });

  it("lists open merge requests for the project", async () => {
    const user = userEvent.setup();
    renderPage();
    await loadProject(user);

    await waitFor(() =>
      expect(screen.getByText(/Add thing/)).toBeInTheDocument(),
    );
  });

  it("starts a review as a background job", async () => {
    // review_merge_request is a multi-round ReAct loop — inline it would block
    // every other RPC, so the handler returns a job_id.
    vi.mocked(client.reviewMr).mockResolvedValue({
      job_id: "job-1",
      project_id: 12,
      mr_iid: 7,
    });
    const user = userEvent.setup();
    renderPage();
    await loadProject(user);
    await waitFor(() =>
      expect(screen.getByText(/Add thing/)).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /review/i }));

    await waitFor(() => expect(client.reviewMr).toHaveBeenCalledWith(12, 7));
    await waitFor(() =>
      expect(screen.getByText(/runs in the background/i)).toBeInTheDocument(),
    );
  });

  it("says an MR is QUEUED FOR APPROVAL, never that it was created", async () => {
    // The web endpoint opens the MR immediately. Here it is an EXTERNAL,
    // irreversible proposal — claiming it exists in GitLab would be false.
    vi.mocked(client.proposeMr).mockResolvedValue(PROPOSAL);
    const user = userEvent.setup();
    renderPage();
    await loadProject(user);

    await user.type(screen.getByLabelText(/issue iid/i), "45");
    await user.click(screen.getByRole("button", { name: /propose mr/i }));

    await waitFor(() =>
      expect(client.proposeMr).toHaveBeenCalledWith(12, 45, undefined),
    );
    await waitFor(() =>
      expect(screen.getByText(/queued for approval/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/nothing has been created/i)).toBeInTheDocument();
  });

  it("posts an operator comment immediately", async () => {
    vi.mocked(client.commentOnMr).mockResolvedValue({ posted: true });
    const user = userEvent.setup();
    renderPage();
    await loadProject(user);
    await waitFor(() =>
      expect(screen.getByText(/Add thing/)).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /comment/i }));
    await user.type(screen.getByLabelText(/^comment$/i), "LGTM");
    await user.click(screen.getByRole("button", { name: /post/i }));

    await waitFor(() =>
      expect(client.commentOnMr).toHaveBeenCalledWith(12, 7, "LGTM"),
    );
  });

  it("surfaces a failed listing", async () => {
    vi.mocked(client.listOpenMrs).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "401 Unauthorized" },
    });
    const user = userEvent.setup();
    renderPage();
    await loadProject(user);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/401/),
    );
  });
});
