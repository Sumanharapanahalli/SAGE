import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listAgents: vi.fn(),
  getAgent: vi.fn(),
}));

import * as client from "@/api/client";
import { Agents } from "@/pages/Agents";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";
import type { Agent } from "@/api/types";

const a1: Agent = {
  name: "analyst",
  kind: "core",
  description: "analyzes",
  system_prompt: "You are an analyst.",
  event_count: 1,
  last_active: null,
};

describe("Agents page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the roster", async () => {
    vi.mocked(client.listAgents).mockResolvedValue([a1]);
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/analyst/i)).toBeInTheDocument(),
    );
  });

  it("shows empty state when no agents", async () => {
    vi.mocked(client.listAgents).mockResolvedValue([]);
    render(<Agents />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/no agents/i)).toBeInTheDocument(),
    );
  });
});
