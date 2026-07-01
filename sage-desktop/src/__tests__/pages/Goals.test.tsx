import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Goals from "@/pages/Goals";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listGoals: vi.fn(),
    createGoal: vi.fn(),
    updateGoal: vi.fn(),
    deleteGoal: vi.fn(),
  };
});

const GOAL = {
  id: "1",
  user_id: "desktop-operator",
  solution: "",
  title: "Ship desktop parity",
  quarter: "2026-Q3",
  status: "on_track",
  owner: "harish",
  key_results: [{ text: "Ship Goals page", done: false }, { text: "Ship tests", done: true }],
  created_at: "",
  updated_at: "",
};

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Goals />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Goals page", () => {
  beforeEach(() => vi.resetAllMocks());

  it("renders the goal list with quarter, status, owner, and key results count", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([GOAL] as any);
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Ship desktop parity")).toBeInTheDocument(),
    );
    const row = screen.getByText("Ship desktop parity").closest("div")!
      .parentElement as HTMLElement;
    expect(within(row).getByText(/2026-Q3/)).toBeInTheDocument();
    expect(within(row).getByText(/on_track/)).toBeInTheDocument();
    expect(within(row).getByText(/harish/)).toBeInTheDocument();
    expect(within(row).getByText(/2 key results/)).toBeInTheDocument();
  });

  it("shows an empty state when there are no goals", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([]);
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/no goals/i)).toBeInTheDocument(),
    );
  });

  it("creates a new goal via the form", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([]);
    vi.mocked(client.createGoal).mockResolvedValue({
      ...GOAL,
      id: "new",
      title: "New objective",
    } as any);
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/title/i), "New objective");
    await user.type(screen.getByLabelText(/quarter/i), "2026-Q4");
    await user.type(screen.getByLabelText(/owner/i), "alice");
    await user.click(screen.getByRole("button", { name: /create/i }));

    await waitFor(() =>
      expect(client.createGoal).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "New objective",
          quarter: "2026-Q4",
          owner: "alice",
        }),
      ),
    );
  });

  it("deletes a goal when the delete action is clicked", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([GOAL] as any);
    vi.mocked(client.deleteGoal).mockResolvedValue({ deleted: true });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Ship desktop parity")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /delete/i }));

    await waitFor(() =>
      expect(client.deleteGoal).toHaveBeenCalledWith("1"),
    );
  });

  it("shows an error banner when creating a goal fails", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([]);
    vi.mocked(client.createGoal).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "title required" },
    });
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/title/i), "x");
    await user.type(screen.getByLabelText(/quarter/i), "2026-Q4");
    await user.click(screen.getByRole("button", { name: /create/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
  });
});
