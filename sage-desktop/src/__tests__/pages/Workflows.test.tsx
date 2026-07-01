import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Workflows from "@/pages/Workflows";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listWorkflows: vi.fn(),
    runWorkflow: vi.fn(),
    resumeWorkflow: vi.fn(),
    getWorkflowStatus: vi.fn(),
  };
});

const WORKFLOWS = {
  workflows: [{ name: "analysis_workflow" }],
  count: 1,
};

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Workflows />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Workflows page", () => {
  beforeEach(() => vi.resetAllMocks());

  it("shows an empty state when no workflows are registered", async () => {
    vi.mocked(client.listWorkflows).mockResolvedValue({
      workflows: [],
      count: 0,
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/no workflows available/i)).toBeInTheDocument(),
    );
  });

  it("lists workflows and runs one with parsed JSON initial state", async () => {
    vi.mocked(client.listWorkflows).mockResolvedValue(WORKFLOWS);
    vi.mocked(client.runWorkflow).mockResolvedValue({
      run_id: "r1",
      status: "completed",
      workflow_name: "analysis_workflow",
      result: { ok: true },
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("analysis_workflow")).toBeInTheDocument(),
    );

    const textarea = screen.getByLabelText(/initial state/i);
    fireEvent.change(textarea, { target: { value: '{"task": "x"}' } });

    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() =>
      expect(client.runWorkflow).toHaveBeenCalledWith("analysis_workflow", {
        task: "x",
      }),
    );
    await waitFor(() =>
      expect(screen.getByText("r1")).toBeInTheDocument(),
    );
    expect(screen.getByText("completed")).toBeInTheDocument();
  });

  it("shows an inline error for invalid JSON and does not call runWorkflow", async () => {
    vi.mocked(client.listWorkflows).mockResolvedValue(WORKFLOWS);
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("analysis_workflow")).toBeInTheDocument(),
    );

    const textarea = screen.getByLabelText(/initial state/i);
    fireEvent.change(textarea, { target: { value: "not json" } });
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() =>
      expect(screen.getByText(/must be valid json/i)).toBeInTheDocument(),
    );
    expect(client.runWorkflow).not.toHaveBeenCalled();
  });

  it("shows a resume form when a run is awaiting approval, and resumes with parsed feedback", async () => {
    vi.mocked(client.listWorkflows).mockResolvedValue(WORKFLOWS);
    vi.mocked(client.runWorkflow).mockResolvedValue({
      run_id: "r1",
      status: "awaiting_approval",
      workflow_name: "analysis_workflow",
      result: {},
    });
    vi.mocked(client.resumeWorkflow).mockResolvedValue({
      run_id: "r1",
      status: "completed",
      workflow_name: "analysis_workflow",
      result: { ok: true },
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("analysis_workflow")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /run/i }));

    await waitFor(() =>
      expect(screen.getByText("awaiting_approval")).toBeInTheDocument(),
    );

    const feedbackBox = screen.getByLabelText(/feedback/i);
    fireEvent.change(feedbackBox, { target: { value: '{"approved": true}' } });
    await user.click(screen.getByRole("button", { name: /resume/i }));

    await waitFor(() =>
      expect(client.resumeWorkflow).toHaveBeenCalledWith("r1", {
        approved: true,
      }),
    );
    await waitFor(() =>
      expect(screen.getByText("completed")).toBeInTheDocument(),
    );
    expect(screen.queryByLabelText(/feedback/i)).not.toBeInTheDocument();
  });

  it("fetches status on demand via the Refresh status button (manual refetch on an always-disabled query)", async () => {
    vi.mocked(client.listWorkflows).mockResolvedValue(WORKFLOWS);
    vi.mocked(client.runWorkflow).mockResolvedValue({
      run_id: "r1",
      status: "completed",
      workflow_name: "analysis_workflow",
      result: {},
    });
    vi.mocked(client.getWorkflowStatus).mockResolvedValue({
      run_id: "r1",
      workflow_name: "analysis_workflow",
      status: "completed",
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("analysis_workflow")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /run/i }));
    await waitFor(() => expect(screen.getByText("r1")).toBeInTheDocument());

    // useWorkflowStatus is wired with enabled=false (manual refresh only) —
    // confirm refetch() still fires the queryFn on a permanently-disabled
    // query, and that its result renders.
    expect(client.getWorkflowStatus).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /refresh status/i }));

    await waitFor(() =>
      expect(client.getWorkflowStatus).toHaveBeenCalledWith("r1"),
    );
    await waitFor(() =>
      expect(screen.getByText(/last checked/i)).toBeInTheDocument(),
    );
  });

  it("renders an error banner when the workflow list fails to load", async () => {
    vi.mocked(client.listWorkflows).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "sidecar crashed" },
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument(),
    );
  });
});
