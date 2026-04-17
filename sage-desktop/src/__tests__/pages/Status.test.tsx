import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getStatus: vi.fn(),
  handshake: vi.fn(),
}));

import * as client from "@/api/client";
import { Status } from "@/pages/Status";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("Status page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders health, project, and pending count", async () => {
    vi.mocked(client.getStatus).mockResolvedValue({
      health: "ok",
      sidecar_version: "0.1.0",
      project: { name: "medtech", path: "/sol/medtech" },
      llm: { provider: "gemini", model: "gemini-2.0" },
      pending_approvals: 3,
    });
    render(<Status />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() => expect(screen.getByText(/medtech/)).toBeInTheDocument());
    expect(screen.getByText(/gemini/)).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument();
  });

  it("shows offline when status fails", async () => {
    vi.mocked(client.getStatus).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "stream closed" },
    });
    render(<Status />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i),
    );
  });
});
