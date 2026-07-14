import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  getStatus: vi.fn(),
  handshake: vi.fn(),
  getQueueStatus: vi.fn(),
}));

import * as client from "@/api/client";
import { Status } from "@/pages/Status";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

// Status now renders a <Link>, so it needs a Router in context.
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
    vi.mocked(client.getQueueStatus).mockResolvedValue({
      pending: 0, in_progress: 0, completed: 0, failed: 0, blocked: 0, cancelled: 0,
      parallel_enabled: false, max_workers: 0,
    });
    render(<Status />, { wrapper: routerWrapper() });
    await waitFor(() => expect(screen.getByText(/medtech/)).toBeInTheDocument());
    expect(screen.getByText(/gemini/)).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument();
  });

  it("links the pending-approvals tile to /approvals when there are pending items", async () => {
    vi.mocked(client.getStatus).mockResolvedValue({
      health: "ok",
      sidecar_version: "0.1.0",
      project: { name: "medtech", path: "/sol/medtech" },
      llm: { provider: "gemini", model: "gemini-2.0" },
      pending_approvals: 2,
    });
    vi.mocked(client.getQueueStatus).mockResolvedValue({
      pending: 0, in_progress: 0, completed: 0, failed: 0, blocked: 0, cancelled: 0,
      parallel_enabled: false, max_workers: 0,
    });
    render(<Status />, { wrapper: routerWrapper() });
    const link = await screen.findByRole("link", { name: /pending approvals/i });
    expect(link).toHaveAttribute("href", "/approvals");
  });

  it("shows offline when status fails", async () => {
    vi.mocked(client.getStatus).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "stream closed" },
    });
    vi.mocked(client.getQueueStatus).mockResolvedValue({
      pending: 0, in_progress: 0, completed: 0, failed: 0, blocked: 0, cancelled: 0,
      parallel_enabled: false, max_workers: 0,
    });
    render(<Status />, { wrapper: routerWrapper() });
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i),
    );
  });
});
