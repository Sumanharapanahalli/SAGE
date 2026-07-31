import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import { ReviewPanel } from "@/components/domain/ReviewPanel";

import { createTestQueryClient } from "../helpers/queryWrapper";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, refineSolution: vi.fn() };
});

const FILES = {
  "project.yaml": "name: imported\ndescription: old description\n",
  "prompts.yaml": "roles: {}\n",
  "tasks.yaml": "task_types: []\n",
};

const SUMMARY = {
  name: "imported",
  description: "old description",
  task_types: [],
  compliance_standards: [],
  integrations: [],
};

const REFINED = {
  solution_name: "imported",
  files: {
    ...FILES,
    "project.yaml": "name: imported\ndescription: a much better description\n",
  },
  summary: { ...SUMMARY, description: "a much better description" },
};

function renderPanel(onAccept = vi.fn()) {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <ReviewPanel
        solutionName="imported"
        files={FILES}
        summary={SUMMARY}
        onAccept={onAccept}
        acceptLabel="Save solution"
        isAccepting={false}
      />
    </QueryClientProvider>,
  );
  return { onAccept };
}

describe("ReviewPanel", () => {
  beforeEach(() => vi.resetAllMocks());

  it("shows the drafted files and summary", () => {
    renderPanel();
    expect(screen.getByText("project.yaml")).toBeInTheDocument();
    expect(screen.getAllByText(/old description/).length).toBeGreaterThan(0);
  });

  it("does not refine on mount", () => {
    renderPanel();
    expect(client.refineSolution).not.toHaveBeenCalled();
  });

  it("requires feedback before refining", () => {
    renderPanel();
    expect(screen.getByRole("button", { name: /refine/i })).toBeDisabled();
  });

  it("sends the current files and feedback to refine", async () => {
    vi.mocked(client.refineSolution).mockResolvedValue(REFINED);
    const user = userEvent.setup();
    renderPanel();

    await user.type(
      screen.getByLabelText(/feedback/i),
      "make the description better",
    );
    await user.click(screen.getByRole("button", { name: /refine/i }));

    await waitFor(() =>
      expect(client.refineSolution).toHaveBeenCalledWith(
        "imported",
        FILES,
        "make the description better",
      ),
    );
  });

  it("replaces the drafts with the refined ones", async () => {
    vi.mocked(client.refineSolution).mockResolvedValue(REFINED);
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText(/feedback/i), "better please");
    await user.click(screen.getByRole("button", { name: /refine/i }));

    await waitFor(() =>
      expect(
        screen.getAllByText(/a much better description/).length,
      ).toBeGreaterThan(0),
    );
  });

  it("clears the feedback box after a successful refine", async () => {
    // The loop: an un-cleared box invites accidentally re-sending the same
    // feedback against already-revised drafts.
    vi.mocked(client.refineSolution).mockResolvedValue(REFINED);
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText(/feedback/i), "better please");
    await user.click(screen.getByRole("button", { name: /refine/i }));

    await waitFor(() =>
      expect(screen.getByLabelText(/feedback/i)).toHaveValue(""),
    );
  });

  it("feeds refined output back into the next refine — the loop", async () => {
    vi.mocked(client.refineSolution).mockResolvedValue(REFINED);
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText(/feedback/i), "first pass");
    await user.click(screen.getByRole("button", { name: /refine/i }));
    await waitFor(() =>
      expect(
        screen.getAllByText(/a much better description/).length,
      ).toBeGreaterThan(0),
    );

    await user.type(screen.getByLabelText(/feedback/i), "second pass");
    await user.click(screen.getByRole("button", { name: /refine/i }));

    await waitFor(() => {
      const calls = vi.mocked(client.refineSolution).mock.calls;
      expect(calls.length).toBe(2);
      // Second call must carry the REFINED files, not the originals.
      expect(calls[1][1]).toEqual(REFINED.files);
      expect(calls[1][2]).toBe("second pass");
    });
  });

  it("accepts the CURRENT drafts, including refinements", async () => {
    vi.mocked(client.refineSolution).mockResolvedValue(REFINED);
    const user = userEvent.setup();
    const { onAccept } = renderPanel();

    await user.type(screen.getByLabelText(/feedback/i), "better please");
    await user.click(screen.getByRole("button", { name: /refine/i }));
    await waitFor(() =>
      expect(
        screen.getAllByText(/a much better description/).length,
      ).toBeGreaterThan(0),
    );
    await user.click(screen.getByRole("button", { name: /save solution/i }));

    expect(onAccept).toHaveBeenCalledWith(REFINED.files);
  });

  it("surfaces a refine failure and keeps the current drafts", async () => {
    vi.mocked(client.refineSolution).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "LLM unavailable: provider down" },
    });
    const user = userEvent.setup();
    renderPanel();

    await user.type(screen.getByLabelText(/feedback/i), "better please");
    await user.click(screen.getByRole("button", { name: /refine/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/provider down/i),
    );
    // A failed refine must not lose the drafts the operator already has.
    expect(screen.getAllByText(/old description/).length).toBeGreaterThan(0);
  });
});
