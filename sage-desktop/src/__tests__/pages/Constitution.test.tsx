import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  constitutionGet: vi.fn(),
  constitutionUpdate: vi.fn(),
  constitutionCheckAction: vi.fn(),
}));

import * as client from "@/api/client";
import Constitution from "@/pages/Constitution";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

const STATE = {
  data: {
    meta: { name: "demo", version: 1, last_updated: "", updated_by: "" },
    principles: [{ id: "p1", text: "Test first", weight: 0.8 }],
    constraints: ["Never touch /prod/"],
  },
  stats: {
    is_empty: false,
    name: "demo",
    version: 1,
    principle_count: 1,
    constraint_count: 1,
    non_negotiable_count: 0,
    has_voice: false,
    has_decisions: false,
    has_knowledge: false,
    history_entries: 0,
  },
  preamble: "## Solution Constitution\n- Test first",
  history: [],
  errors: [],
};

describe("Constitution page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads the constitution and renders editors, preamble, and meta", async () => {
    vi.mocked(client.constitutionGet).mockResolvedValue(STATE);
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <Constitution />
      </Wrapper>,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("principle 1 text")).toHaveValue(
        "Test first",
      ),
    );
    expect(screen.getByText(/v1/)).toBeInTheDocument();
    expect(screen.getByText(/1 principles · 1 constraints/i)).toBeInTheDocument();
    expect(screen.getByTestId("preamble-preview")).toHaveTextContent(
      /Solution Constitution/,
    );
  });

  it("enables Save once the draft diverges and posts the update", async () => {
    vi.mocked(client.constitutionGet).mockResolvedValue(STATE);
    vi.mocked(client.constitutionUpdate).mockResolvedValue({
      stats: { ...STATE.stats, version: 2 },
      preamble: STATE.preamble,
      version: 2,
      path: "/tmp/demo/constitution.yaml",
    });
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <Constitution />
      </Wrapper>,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("principle 1 text")).toHaveValue(
        "Test first",
      ),
    );
    const save = screen.getByRole("button", { name: /^save$/i });
    expect(save).toBeDisabled();

    fireEvent.change(screen.getByLabelText("principle 1 text"), {
      target: { value: "Test first, always" },
    });
    expect(save).toBeEnabled();
    fireEvent.click(save);

    await waitFor(() =>
      expect(client.constitutionUpdate).toHaveBeenCalledTimes(1),
    );
    const [data] = vi.mocked(client.constitutionUpdate).mock.calls[0];
    expect(data.principles?.[0].text).toBe("Test first, always");
  });
});
