import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import SkillsTools from "@/pages/SkillsTools";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listSkills: vi.fn(),
    setSkillVisibility: vi.fn(),
    reloadSkills: vi.fn(),
    listMcpTools: vi.fn(),
  };
});

const SKILLS_RESULT = {
  skills: [
    {
      name: "tdd",
      version: "1.0.0",
      visibility: "public",
      roles: ["developer"],
      runner: "software",
      description: "Test-driven development discipline",
      tools: [],
      prompt: "",
      acceptance_criteria: [],
      certifications: [],
      engines: [],
      tags: [],
    },
  ],
  stats: {
    total: 1,
    active: 1,
    public: 1,
    private: 0,
    disabled: 0,
    roles_covered: 1,
    runners_covered: 1,
    loaded_dirs: ["skills/public"],
  },
};

const MCP_RESULT = {
  tools: [
    { name: "flash_firmware", description: "Flash a firmware image", server: "firmware" },
  ],
  count: 1,
};

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <SkillsTools />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SkillsTools page", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists skills with their visibility and MCP tools", async () => {
    vi.mocked(client.listSkills).mockResolvedValue(SKILLS_RESULT);
    vi.mocked(client.listMcpTools).mockResolvedValue(MCP_RESULT);
    renderPage();

    await waitFor(() => expect(screen.getByText("tdd")).toBeInTheDocument());
    expect(
      screen.getByText(/Test-driven development discipline/i),
    ).toBeInTheDocument();
    expect(screen.getByText("flash_firmware")).toBeInTheDocument();
    expect(screen.getByText(/Flash a firmware image/i)).toBeInTheDocument();
  });

  it("changes a skill's visibility and refreshes the list", async () => {
    vi.mocked(client.listSkills).mockResolvedValue(SKILLS_RESULT);
    vi.mocked(client.listMcpTools).mockResolvedValue(MCP_RESULT);
    vi.mocked(client.setSkillVisibility).mockResolvedValue({
      status: "updated",
      name: "tdd",
      visibility: "private",
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("tdd")).toBeInTheDocument());
    const row = screen.getByText("tdd").closest("tr") ?? screen.getByText("tdd").closest("div");
    const select = within(row as HTMLElement).getByRole("combobox");
    await user.selectOptions(select, "private");

    await waitFor(() =>
      expect(client.setSkillVisibility).toHaveBeenCalledWith("tdd", "private"),
    );
    await waitFor(() => expect(client.listSkills).toHaveBeenCalledTimes(2));
  });

  it("reloads skills on demand", async () => {
    vi.mocked(client.listSkills).mockResolvedValue(SKILLS_RESULT);
    vi.mocked(client.listMcpTools).mockResolvedValue(MCP_RESULT);
    vi.mocked(client.reloadSkills).mockResolvedValue({
      status: "reloaded",
      skills_loaded: 21,
      stats: SKILLS_RESULT.stats,
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => expect(screen.getByText("tdd")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: /reload/i }));

    await waitFor(() => expect(client.reloadSkills).toHaveBeenCalled());
    await waitFor(() => expect(client.listSkills).toHaveBeenCalledTimes(2));
  });

  it("renders an error banner when listing skills fails", async () => {
    vi.mocked(client.listSkills).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "sidecar crashed" },
    });
    vi.mocked(client.listMcpTools).mockResolvedValue(MCP_RESULT);
    renderPage();

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByText(/sidecar crashed/i)).toBeInTheDocument();
  });
});
