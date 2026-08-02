import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import { OrgTemplateChooser } from "@/components/domain/OrgTemplateChooser";

import { createTestQueryClient } from "../helpers/queryWrapper";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, fetchOrgTemplates: vi.fn() };
});

const TEMPLATES = {
  templates: [
    {
      id: "starter",
      name: "General Engineering Team",
      description: "Works for any software domain",
      role_count: 2,
      compliance_standards: [],
      icon: "⚙️",
      roles: [
        { key: "analyst", name: "Signal Analyst", description: "Triage logs" },
        { key: "developer", name: "Code Reviewer", description: "Review MRs" },
      ],
    },
    {
      id: "medtech",
      name: "Medical Device Team",
      description: "ISO 13485 / IEC 62304",
      role_count: 1,
      compliance_standards: ["ISO 13485", "IEC 62304"],
      icon: "🩺",
      roles: [
        { key: "regulatory", name: "Regulatory Affairs", description: "Submissions" },
      ],
    },
  ],
};

/** `.at()` is not in this project's tsconfig lib target. */
function lastChoice(onChange: ReturnType<typeof vi.fn>) {
  const calls = onChange.mock.calls;
  return calls[calls.length - 1][0];
}

function renderChooser() {
  const onChange = vi.fn();
  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <OrgTemplateChooser onChange={onChange} />
    </QueryClientProvider>,
  );
  return { onChange };
}

describe("OrgTemplateChooser", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.fetchOrgTemplates).mockResolvedValue(TEMPLATES);
  });

  it("lists the available templates", async () => {
    renderChooser();
    await waitFor(() =>
      expect(screen.getByText(/general engineering team/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/medical device team/i)).toBeInTheDocument();
  });

  it("emits nothing until a template is picked", async () => {
    const { onChange } = renderChooser();
    await waitFor(() =>
      expect(screen.getByText(/general engineering team/i)).toBeInTheDocument(),
    );
    expect(onChange).not.toHaveBeenCalled();
  });

  it("emits a brief naming every enabled role", async () => {
    const user = userEvent.setup();
    const { onChange } = renderChooser();
    await waitFor(() =>
      expect(screen.getByText(/general engineering team/i)).toBeInTheDocument(),
    );
    await user.click(screen.getByText(/general engineering team/i));

    await waitFor(() => expect(onChange).toHaveBeenCalled());
    const choice = lastChoice(onChange);
    expect(choice.templateId).toBe("starter");
    expect(choice.enabledRoles).toEqual(["analyst", "developer"]);
    // The brief is what actually reaches the LLM as org_context.
    expect(choice.brief).toContain("analyst");
    expect(choice.brief).toContain("developer");
  });

  it("carries the template's compliance standards", async () => {
    const user = userEvent.setup();
    const { onChange } = renderChooser();
    await waitFor(() =>
      expect(screen.getByText(/medical device team/i)).toBeInTheDocument(),
    );
    await user.click(screen.getByText(/medical device team/i));

    await waitFor(() => expect(onChange).toHaveBeenCalled());
    expect(lastChoice(onChange).complianceStandards).toEqual([
      "ISO 13485",
      "IEC 62304",
    ]);
  });

  it("drops a role from the brief when it is unchecked", async () => {
    const user = userEvent.setup();
    const { onChange } = renderChooser();
    await waitFor(() =>
      expect(screen.getByText(/general engineering team/i)).toBeInTheDocument(),
    );
    await user.click(screen.getByText(/general engineering team/i));
    await waitFor(() => expect(onChange).toHaveBeenCalled());

    await user.click(screen.getByRole("checkbox", { name: /signal analyst/i }));

    await waitFor(() => {
      const choice = lastChoice(onChange);
      expect(choice.enabledRoles).toEqual(["developer"]);
      expect(choice.brief).not.toContain("analyst");
    });
  });

  it("clears the choice when the selected template is clicked again", async () => {
    // Starting from no template is a valid choice; without this there is no
    // way back to it.
    const user = userEvent.setup();
    const { onChange } = renderChooser();
    await waitFor(() =>
      expect(screen.getByText(/general engineering team/i)).toBeInTheDocument(),
    );
    await user.click(screen.getByText(/general engineering team/i));
    await waitFor(() => expect(onChange).toHaveBeenCalled());
    await user.click(screen.getByText(/general engineering team/i));

    await waitFor(() =>
      expect(lastChoice(onChange)).toBeNull(),
    );
  });

  it("renders nothing when no templates ship", async () => {
    vi.mocked(client.fetchOrgTemplates).mockResolvedValue({ templates: [] });
    const { onChange } = renderChooser();
    await waitFor(() =>
      expect(
        screen.queryByText(/start from a team structure/i),
      ).not.toBeInTheDocument(),
    );
    expect(onChange).not.toHaveBeenCalled();
  });
});
