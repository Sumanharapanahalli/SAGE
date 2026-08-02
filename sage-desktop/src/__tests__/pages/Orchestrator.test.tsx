import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import Orchestrator from "@/pages/Orchestrator";

import { createTestQueryClient } from "../helpers/queryWrapper";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, orchestratorStats: vi.fn(), orchestratorRecent: vi.fn() };
});

const STATS = {
  modules: {
    events: { published: 12 },
    budget: {},
    reflection: { runs: 3 },
    plans: {},
    spawns: {},
    tools: {},
    backtrack: {},
    consensus: {},
    memory_planner: {},
  },
  unavailable: ["consensus"],
};

function renderPage() {
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <Orchestrator />
    </QueryClientProvider>,
  );
}

describe("Orchestrator page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.orchestratorStats).mockResolvedValue(STATS);
    vi.mocked(client.orchestratorRecent).mockResolvedValue({
      module: "events",
      items: [{ id: "e1", type: "task.started" }],
      available: true,
    });
  });

  it("shows a tile for all nine modules", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/event bus/i)).toBeInTheDocument(),
    );
    for (const label of [
      /budget/i,
      /reflection/i,
      /beam search/i,
      /agent spawner/i,
      /tools/i,
      /backtrack/i,
      /consensus/i,
      /memory planner/i,
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("renders each module's counters", async () => {
    renderPage();
    await waitFor(() => expect(screen.getByText("12")).toBeInTheDocument());
    expect(screen.getByText("published")).toBeInTheDocument();
  });

  it("labels an unavailable module 'not active', not zero", async () => {
    // A row of zeroes would read as "ran, did nothing" — misleading for a
    // subsystem that simply is not loaded on this install.
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/not active/i)).toBeInTheDocument(),
    );
  });

  it("does not offer Recent for a stats-only module", async () => {
    renderPage();
    // Wait on something that only appears once stats RESOLVE — the tiles
    // themselves render immediately, so waiting on a label would assert
    // against the pre-data state where nothing is marked unavailable yet.
    await waitFor(() =>
      expect(screen.getByText(/not active/i)).toBeInTheDocument(),
    );
    // 7 modules expose recent records; budget and memory_planner do not, and
    // consensus is unavailable here.
    expect(screen.getAllByRole("button", { name: /recent/i })).toHaveLength(6);
  });

  it("loads recent records on demand only", async () => {
    const user = userEvent.setup();
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/event bus/i)).toBeInTheDocument(),
    );
    expect(client.orchestratorRecent).not.toHaveBeenCalled();

    await user.click(screen.getAllByRole("button", { name: /recent/i })[0]);

    await waitFor(() =>
      expect(client.orchestratorRecent).toHaveBeenCalledWith("events"),
    );
    await waitFor(() =>
      expect(screen.getByText(/task.started/)).toBeInTheDocument(),
    );
  });

  it("surfaces a stats failure", async () => {
    vi.mocked(client.orchestratorStats).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "sidecar offline" },
    });
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar offline/i),
    );
  });
});
