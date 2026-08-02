import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import Code from "@/pages/Code";

import { createTestQueryClient } from "../helpers/queryWrapper";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    codePlan: vi.fn(),
    codeApprove: vi.fn(),
    codeExecute: vi.fn(),
    codeSandboxStatus: vi.fn(),
  };
});

const PLAN = {
  run_id: "run-1",
  status: "awaiting_approval",
  plan: "read the file, count rows",
  code: "print('hi')",
};

function renderPage() {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <Code />
    </QueryClientProvider>,
  );
}

async function makePlan(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/task/i), "count rows");
  await user.click(screen.getByRole("button", { name: /^plan$/i }));
  // The Approve button only exists once a plan has come back — an unambiguous
  // signal, unlike the plan text, which overlaps the task the user typed.
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument(),
  );
}

describe("Code page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.codeSandboxStatus).mockResolvedValue({
      docker_available: true,
      sandbox: "docker",
      isolated: true,
    });
  });

  it("plans nothing on mount", () => {
    renderPage();
    expect(client.codePlan).not.toHaveBeenCalled();
  });

  it("requires a task before planning", () => {
    renderPage();
    expect(screen.getByRole("button", { name: /^plan$/i })).toBeDisabled();
  });

  it("shows the drafted code before anything runs", async () => {
    vi.mocked(client.codePlan).mockResolvedValue(PLAN);
    const user = userEvent.setup();
    renderPage();
    await makePlan(user);

    expect(screen.getByText("print('hi')")).toBeInTheDocument();
    expect(client.codeExecute).not.toHaveBeenCalled();
  });

  it("keeps Execute disabled until the plan is approved", async () => {
    vi.mocked(client.codePlan).mockResolvedValue(PLAN);
    const user = userEvent.setup();
    renderPage();
    await makePlan(user);

    expect(screen.getByRole("button", { name: /execute/i })).toBeDisabled();
  });

  it("enables and runs Execute once approved", async () => {
    vi.mocked(client.codePlan).mockResolvedValue(PLAN);
    vi.mocked(client.codeApprove).mockResolvedValue({
      run_id: "run-1",
      status: "approved",
    });
    vi.mocked(client.codeExecute).mockResolvedValue({
      run_id: "run-1",
      status: "completed",
      output: { stdout: "hi\n", stderr: "", returncode: 0, sandbox: "docker" },
    });
    const user = userEvent.setup();
    renderPage();
    await makePlan(user);

    await user.click(screen.getByRole("button", { name: /approve/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /execute/i })).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: /execute/i }));

    await waitFor(() =>
      expect(client.codeExecute).toHaveBeenCalledWith("run-1"),
    );
    // Not /hi/ — the drafted code block is `print('hi')`, so that matches twice.
    await waitFor(() =>
      expect(screen.getByText(/exit 0/i)).toBeInTheDocument(),
    );
  });

  it("warns about missing isolation BEFORE the operator approves", async () => {
    // The runner falls back to an unisolated local subprocess without Docker.
    // The web UI only reveals that after the code has already run.
    vi.mocked(client.codeSandboxStatus).mockResolvedValue({
      docker_available: false,
      sandbox: "local_subprocess",
      isolated: false,
      warning:
        "Docker is not available — approved code will run in a local subprocess on this machine, with no isolation.",
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/no isolation/i),
    );
    // Shown before any plan exists, i.e. before there is anything to approve.
    expect(
      screen.queryByRole("button", { name: /approve/i }),
    ).not.toBeInTheDocument();
  });

  it("surfaces a refused execution", async () => {
    vi.mocked(client.codePlan).mockResolvedValue(PLAN);
    vi.mocked(client.codeApprove).mockResolvedValue({
      run_id: "run-1",
      status: "approved",
    });
    vi.mocked(client.codeExecute).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "Run 'run-1' has not been approved" },
    });
    const user = userEvent.setup();
    renderPage();
    await makePlan(user);
    await user.click(screen.getByRole("button", { name: /approve/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /execute/i })).toBeEnabled(),
    );
    await user.click(screen.getByRole("button", { name: /execute/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/not been approved/i),
    );
  });
});
