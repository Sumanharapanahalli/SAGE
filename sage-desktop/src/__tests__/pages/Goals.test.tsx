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

  it("updates a goal's status when a new status is selected", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([GOAL] as any);
    vi.mocked(client.updateGoal).mockResolvedValue({
      ...GOAL,
      status: "at_risk",
    } as any);
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Ship desktop parity")).toBeInTheDocument(),
    );
    await user.selectOptions(screen.getByLabelText(/status for/i), "at_risk");

    await waitFor(() =>
      expect(client.updateGoal).toHaveBeenCalledWith(
        expect.objectContaining({ goal_id: "1", status: "at_risk" }),
      ),
    );
  });

  it("requires a confirm step before deleting a goal", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([GOAL] as any);
    vi.mocked(client.deleteGoal).mockResolvedValue({ deleted: true });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Ship desktop parity")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /^delete$/i }));

    expect(client.deleteGoal).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: /^confirm$/i }),
    ).toBeInTheDocument();
  });

  it("deletes a goal after confirming", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([GOAL] as any);
    vi.mocked(client.deleteGoal).mockResolvedValue({ deleted: true });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Ship desktop parity")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /^delete$/i }));
    await user.click(screen.getByRole("button", { name: /^confirm$/i }));

    await waitFor(() =>
      expect(client.deleteGoal).toHaveBeenCalledWith("1"),
    );
  });

  it("shows an alert when the goal list fails to load", async () => {
    vi.mocked(client.listGoals).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "sidecar down" },
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument(),
    );
  });

  it("shows an alert when deleting a goal fails", async () => {
    vi.mocked(client.listGoals).mockResolvedValue([GOAL] as any);
    vi.mocked(client.deleteGoal).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "delete boom" },
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Ship desktop parity")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /^delete$/i }));
    await user.click(screen.getByRole("button", { name: /^confirm$/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/delete boom/i),
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
