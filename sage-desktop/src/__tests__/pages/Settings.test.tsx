import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Settings from "@/pages/Settings";

vi.mock("@/api/client");

describe("Settings page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("renders current provider info", async () => {
    vi.mocked(client.getLlmInfo).mockResolvedValue({
      provider_name: "GeminiCLIProvider",
      model: "gemini-2.0-flash-001",
      available_providers: ["gemini", "ollama"],
    });
    vi.mocked(client.listSolutions).mockResolvedValue([]);
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Settings />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText(/GeminiCLIProvider/)).toBeInTheDocument());
  });

  it("unloads the active solution and forgets it", async () => {
    vi.mocked(client.getLlmInfo).mockResolvedValue({
      provider_name: "GeminiCLIProvider",
      model: "gemini-2.0-flash-001",
      available_providers: ["gemini"],
    });
    vi.mocked(client.listSolutions).mockResolvedValue([
      { name: "yoga", path: "/abs/yoga", has_sage_dir: true },
    ]);
    vi.mocked(client.getCurrentSolution).mockResolvedValue({
      name: "yoga",
      path: "/abs/yoga",
    });
    vi.mocked(client.unloadSolution).mockResolvedValue({
      name: null,
      path: null,
    });
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: "yoga", path: "/abs/yoga" }),
    );

    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Settings />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const btn = await screen.findByRole("button", { name: /unload solution/i });
    await waitFor(() => expect(btn).not.toBeDisabled());
    fireEvent.click(btn);

    await waitFor(() => expect(client.unloadSolution).toHaveBeenCalled());
    await waitFor(() =>
      expect(localStorage.getItem("sage-desktop:last-solution")).toBeNull(),
    );
  });

  it("disables Unload when no solution is active", async () => {
    vi.mocked(client.getLlmInfo).mockResolvedValue({
      provider_name: "GeminiCLIProvider",
      model: "gemini-2.0-flash-001",
      available_providers: ["gemini"],
    });
    vi.mocked(client.listSolutions).mockResolvedValue([]);
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Settings />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const btn = await screen.findByRole("button", { name: /unload solution/i });
    expect(btn).toBeDisabled();
  });

  it("renders the solution picker section", async () => {
    vi.mocked(client.getLlmInfo).mockResolvedValue({
      provider_name: "GeminiCLIProvider",
      model: "gemini-2.0-flash-001",
      available_providers: ["gemini"],
    });
    vi.mocked(client.listSolutions).mockResolvedValue([
      { name: "yoga", path: "/abs/yoga", has_sage_dir: false },
    ]);
    vi.mocked(client.getCurrentSolution).mockResolvedValue(null);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Settings />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("solution-picker")).toBeInTheDocument());
    expect(screen.getByRole("option", { name: /yoga/i })).toBeInTheDocument();
  });
});
