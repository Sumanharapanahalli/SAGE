import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  knowledgeList: vi.fn(),
  knowledgeSearch: vi.fn(),
  knowledgeStats: vi.fn(),
  knowledgeAdd: vi.fn(),
  knowledgeDelete: vi.fn(),
}));

import * as client from "@/api/client";
import Knowledge from "@/pages/Knowledge";

import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

const STATS_FULL = {
  total: 2,
  collection: "demo_knowledge",
  backend: "full" as const,
  solution: "demo",
};

const LIST_TWO = {
  entries: [
    { id: "u1", text: "first entry", metadata: {} },
    { id: "u2", text: "second entry", metadata: { tag: "x" } },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

describe("Knowledge page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders header stats and the browse list", async () => {
    vi.mocked(client.knowledgeStats).mockResolvedValue(STATS_FULL);
    vi.mocked(client.knowledgeList).mockResolvedValue(LIST_TWO);
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <Knowledge />
      </Wrapper>,
    );

    await waitFor(() => expect(screen.getByText("first entry")).toBeInTheDocument());
    expect(screen.getByText("demo_knowledge")).toBeInTheDocument();
    expect(screen.getByText(/backend:/)).toHaveTextContent("full");
    expect(screen.getByText(/Showing 1–2 of 2/)).toBeInTheDocument();
  });

  it("shows minimal banner on the search tab when backend is minimal", async () => {
    vi.mocked(client.knowledgeStats).mockResolvedValue({
      ...STATS_FULL,
      backend: "minimal",
    });
    vi.mocked(client.knowledgeList).mockResolvedValue({
      entries: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    const Wrapper = wrapperWith(createTestQueryClient());
    render(
      <Wrapper>
        <Knowledge />
      </Wrapper>,
    );

    await waitFor(() =>
      expect(screen.getByText(/backend:/)).toHaveTextContent("minimal"),
    );
    fireEvent.click(screen.getByRole("button", { name: /^search$/i }));
    expect(
      screen.getByText(/Semantic search is unavailable/i),
    ).toBeInTheDocument();
  });
});
