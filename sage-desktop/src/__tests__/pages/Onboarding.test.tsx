import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Onboarding from "@/pages/Onboarding";

// importOriginal keeps the real `toDesktopError` (a bare factory would
// auto-mock it and break the ErrorBanner). Only the two calls this page
// makes are stubbed.
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    onboardingGenerate: vi.fn(),
    switchSolution: vi.fn(),
    fetchOrgTemplates: vi.fn(),
  };
});

const CREATED = {
  solution_name: "yoga",
  path: "/repo/solutions/yoga",
  status: "created" as const,
  files: { "project.yaml": "..." },
  suggested_routes: [],
  message: "",
};

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Onboarding />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Onboarding page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    // Ship no templates so OrgTemplateChooser renders nothing here — it would
    // otherwise add a second role="alert". Set AFTER resetAllMocks, which
    // clears anything configured in the module factory; leaving it unset makes
    // the queryFn resolve undefined, which React Query treats as an error.
    vi.mocked(client.fetchOrgTemplates).mockResolvedValue({ templates: [] });
  });

  it("renders the wizard form", () => {
    renderPage();
    expect(
      screen.getByRole("button", { name: /generate/i }),
    ).toBeInTheDocument();
  });

  it("surfaces an error when switching to the created solution fails", async () => {
    vi.mocked(client.onboardingGenerate).mockResolvedValue(CREATED as any);
    vi.mocked(client.switchSolution).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "sidecar respawn failed" },
    });
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByPlaceholderText(/e\.g\. yoga/i), "yoga");
    await user.type(
      screen.getByPlaceholderText(/a short description/i),
      "A yoga studio scheduling and billing helper.",
    );
    await user.click(screen.getByRole("button", { name: /generate/i }));

    // The wizard now shows the created-result view with the switch action.
    const switchBtn = await screen.findByRole("button", {
      name: /switch to it/i,
    });
    await user.click(switchBtn);

    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument(),
    );
  });
});
