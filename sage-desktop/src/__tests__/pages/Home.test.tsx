import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listSolutions: vi.fn(),
  getCurrentSolution: vi.fn(),
  switchSolution: vi.fn(),
  unloadSolution: vi.fn(),
  removeSolution: vi.fn(),
}));

import * as client from "@/api/client";
import Home from "@/pages/Home";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";
import type { SolutionRef } from "@/api/types";

function routerWrapper() {
  const QueryWrapper = wrapperWith(createTestQueryClient());
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter>
        <QueryWrapper>{children}</QueryWrapper>
      </MemoryRouter>
    );
  };
}

const sol = (name: string): SolutionRef => ({
  name,
  path: `/solutions/${name}`,
  has_sage_dir: true,
});

describe("Home page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("shows the solution list", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([
      sol("starter"),
      sol("poseengine"),
    ]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(screen.getByText("poseengine")).toBeInTheDocument(),
    );
    expect(screen.getByText("starter")).toBeInTheDocument();
  });

  it("shows an empty state when there are no solutions", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(screen.getByText(/no solutions found/i)).toBeInTheDocument(),
    );
  });

  it("filters the list by name", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([
      sol("starter"),
      sol("poseengine"),
    ]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() => screen.getByText("poseengine"));
    await userEvent.type(
      screen.getByPlaceholderText(/filter solutions/i),
      "pose",
    );
    expect(screen.getByText("poseengine")).toBeInTheDocument();
    expect(screen.queryByText("starter")).not.toBeInTheDocument();
  });

  it("switches to the picked solution and remembers it", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([sol("poseengine")]);
    vi.mocked(client.switchSolution).mockResolvedValue({
      name: "poseengine",
      path: "/solutions/poseengine",
    });
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() => screen.getByText("poseengine"));
    await userEvent.click(screen.getByText("poseengine"));
    await waitFor(() =>
      expect(client.switchSolution).toHaveBeenCalledWith(
        "poseengine",
        "/solutions/poseengine",
      ),
    );
    await waitFor(() =>
      expect(localStorage.getItem("sage-desktop:last-solution")).toEqual(
        JSON.stringify({ name: "poseengine", path: "/solutions/poseengine" }),
      ),
    );
  });

  it("auto-reopens the remembered solution on mount", async () => {
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: "poseengine", path: "/solutions/poseengine" }),
    );
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([sol("poseengine")]);
    vi.mocked(client.switchSolution).mockResolvedValue({
      name: "poseengine",
      path: "/solutions/poseengine",
    });
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(client.switchSolution).toHaveBeenCalledWith(
        "poseengine",
        "/solutions/poseengine",
      ),
    );
  });

  it("does not auto-reopen when a solution is already active", async () => {
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: "poseengine", path: "/solutions/poseengine" }),
    );
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "starter",
      path: "/solutions/starter",
    });
    vi.mocked(client.listSolutions).mockResolvedValue([
      sol("starter"),
      sol("poseengine"),
    ]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() => screen.getByText("poseengine"));
    expect(client.switchSolution).not.toHaveBeenCalled();
  });

  it("shows an error banner when the list fails to load", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "dead" },
    });
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i),
    );
  });

  it("archives a solution from the picker without switching to it", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([sol("poseengine")]);
    vi.mocked(client.removeSolution).mockResolvedValue({
      name: "poseengine",
      mode: "archive",
      path: "/solutions/poseengine",
      archived_to: "/solutions/.archive/poseengine-20260713T000000Z",
    });
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() => screen.getByText("poseengine"));

    await userEvent.click(
      screen.getByRole("button", { name: /remove poseengine/i }),
    );
    expect(screen.getByTestId("remove-solution-dialog")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^archive$/i }));

    await waitFor(() =>
      expect(client.removeSolution).toHaveBeenCalledWith(
        "poseengine",
        "archive",
        undefined,
      ),
    );
    // Removing must never load the solution.
    expect(client.switchSolution).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(
        screen.queryByTestId("remove-solution-dialog"),
      ).not.toBeInTheDocument(),
    );
  });

  it("requires a typed confirmation before deleting from disk", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([sol("poseengine")]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() => screen.getByText("poseengine"));

    await userEvent.click(
      screen.getByRole("button", { name: /remove poseengine/i }),
    );
    await userEvent.click(
      screen.getByRole("radio", { name: /delete permanently/i }),
    );
    expect(
      screen.getByRole("button", { name: /delete permanently/i }),
    ).toBeDisabled();
    expect(client.removeSolution).not.toHaveBeenCalled();

    await userEvent.type(
      screen.getByLabelText(/type the solution name/i),
      "poseengine",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /delete permanently/i }),
    );
    await waitFor(() =>
      expect(client.removeSolution).toHaveBeenCalledWith(
        "poseengine",
        "delete",
        "poseengine",
      ),
    );
  });

  it("always shows a + New solution link", async () => {
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    vi.mocked(client.listSolutions).mockResolvedValue([]);
    render(<Home />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(
        screen.getByRole("link", { name: /new solution/i }),
      ).toHaveAttribute("href", "/onboarding"),
    );
  });
});
