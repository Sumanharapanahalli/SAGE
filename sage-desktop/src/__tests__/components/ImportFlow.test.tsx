import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import { ImportFlow } from "@/components/domain/ImportFlow";

import { createTestQueryClient } from "../helpers/queryWrapper";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, scanFolder: vi.fn(), saveSolution: vi.fn() };
});

const FILES = {
  "project.yaml": "name: imported\ndescription: an imported codebase\n",
  "prompts.yaml": "roles: {}\n",
  "tasks.yaml": "task_types: []\n",
};

const SCAN_RESULT = {
  solution_name: "imported",
  files: FILES,
  summary: {
    name: "imported",
    description: "an imported codebase",
    task_types: [{ name: "REVIEW", description: "review it" }],
    compliance_standards: [],
    integrations: [],
  },
};

function renderFlow(onSaved = vi.fn()) {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <ImportFlow onSaved={onSaved} />
    </QueryClientProvider>,
  );
  return { onSaved };
}

async function scan(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/folder path/i), "/tmp/codebase");
  await user.type(screen.getByLabelText(/solution name/i), "imported");
  await user.click(screen.getByRole("button", { name: /scan folder/i }));
}

describe("ImportFlow", () => {
  beforeEach(() => vi.resetAllMocks());

  it("does not scan on mount", () => {
    renderFlow();
    expect(client.scanFolder).not.toHaveBeenCalled();
  });

  it("requires a folder path and a solution name before scanning", async () => {
    renderFlow();
    expect(screen.getByRole("button", { name: /scan folder/i })).toBeDisabled();
  });

  it("scans the folder and shows the drafted files", async () => {
    vi.mocked(client.scanFolder).mockResolvedValue(SCAN_RESULT);
    const user = userEvent.setup();
    renderFlow();
    await scan(user);

    await waitFor(() =>
      expect(client.scanFolder).toHaveBeenCalledWith(
        "/tmp/codebase",
        "imported",
        "",
      ),
    );
    await waitFor(() =>
      expect(screen.getByText("project.yaml")).toBeInTheDocument(),
    );
    expect(screen.getByText(/REVIEW/)).toBeInTheDocument();
  });

  it("writes nothing until the operator saves", async () => {
    vi.mocked(client.scanFolder).mockResolvedValue(SCAN_RESULT);
    const user = userEvent.setup();
    renderFlow();
    await scan(user);

    await waitFor(() =>
      expect(screen.getByText("project.yaml")).toBeInTheDocument(),
    );
    // Scanning is a draft step — the write is a separate, explicit decision.
    expect(client.saveSolution).not.toHaveBeenCalled();
  });

  it("saves the drafted triad and reports where it landed", async () => {
    vi.mocked(client.scanFolder).mockResolvedValue(SCAN_RESULT);
    vi.mocked(client.saveSolution).mockResolvedValue({
      status: "saved",
      solution_name: "imported",
      path: "/solutions/imported",
      files_written: ["project.yaml", "prompts.yaml", "tasks.yaml"],
    });
    const user = userEvent.setup();
    const { onSaved } = renderFlow();
    await scan(user);

    await waitFor(() =>
      expect(screen.getByText("project.yaml")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /save solution/i }));

    await waitFor(() =>
      expect(client.saveSolution).toHaveBeenCalledWith("imported", FILES),
    );
    await waitFor(() =>
      expect(screen.getByText(/solutions\/imported/)).toBeInTheDocument(),
    );
    // Both values are needed to switch into the new solution.
    await waitFor(() =>
      expect(onSaved).toHaveBeenCalledWith("imported", "/solutions/imported"),
    );
  });

  it("surfaces a scan failure", async () => {
    vi.mocked(client.scanFolder).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "folder not found: /tmp/codebase" },
    });
    const user = userEvent.setup();
    renderFlow();
    await scan(user);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/folder not found/i),
    );
  });

  it("surfaces a save failure", async () => {
    vi.mocked(client.scanFolder).mockResolvedValue(SCAN_RESULT);
    vi.mocked(client.saveSolution).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "resolved path escapes the solutions directory" },
    });
    const user = userEvent.setup();
    renderFlow();
    await scan(user);
    await waitFor(() =>
      expect(screen.getByText("project.yaml")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /save solution/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/escapes/i),
    );
  });
});
