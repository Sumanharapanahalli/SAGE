import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import Console from "@/pages/Console";
import { createTestQueryClient } from "../helpers/queryWrapper";

// Stub only `tailLogs`: a bare vi.mock("@/api/client") would auto-mock the
// pure `toDesktopError` helper ErrorBanner's consumers rely on.
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, tailLogs: vi.fn() };
});

const entry = (seq: number, message: string, level = "INFO", name = "src.test") => ({
  seq,
  ts: "2026-07-13T10:11:12.345678+00:00",
  level,
  name,
  message,
});

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Console />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Console page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    // jsdom doesn't implement scrollIntoView; the page autoscrolls on every
    // new batch of lines.
    Element.prototype.scrollIntoView = vi.fn();
  });

  it("renders buffered log lines and shows a connected indicator", async () => {
    vi.mocked(client.tailLogs).mockResolvedValue({
      entries: [entry(1, "gateway timeout", "WARNING", "src.core.llm_gateway")],
      last_seq: 1,
      buffered: 1,
      capacity: 500,
      installed: true,
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("gateway timeout")).toBeInTheDocument(),
    );
    expect(screen.getByText("WARNING")).toBeInTheDocument();
    expect(screen.getByText("src.core.llm_gateway")).toBeInTheDocument();
    expect(screen.getByTestId("console-connection")).toHaveTextContent(
      /connected/i,
    );
  });

  it("renders a multi-line traceback as one record", async () => {
    vi.mocked(client.tailLogs).mockResolvedValue({
      entries: [
        entry(
          1,
          "analysis failed\nTraceback (most recent call last):\nValueError: boom",
          "ERROR",
          "src.agents.analyst",
        ),
      ],
      last_seq: 1,
      buffered: 1,
      capacity: 500,
      installed: true,
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/ValueError: boom/)).toBeInTheDocument(),
    );
  });

  it("filters lines by the free-text filter", async () => {
    const user = userEvent.setup();
    vi.mocked(client.tailLogs).mockResolvedValue({
      entries: [entry(1, "keep me"), entry(2, "drop me")],
      last_seq: 2,
      buffered: 2,
      capacity: 500,
      installed: true,
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("drop me")).toBeInTheDocument());

    await user.type(screen.getByPlaceholderText(/filter logs/i), "keep");

    expect(screen.getByText("keep me")).toBeInTheDocument();
    expect(screen.queryByText("drop me")).not.toBeInTheDocument();
  });

  it("filters by minimum level", async () => {
    const user = userEvent.setup();
    vi.mocked(client.tailLogs).mockResolvedValue({
      entries: [entry(1, "chatty", "INFO"), entry(2, "bad", "ERROR")],
      last_seq: 2,
      buffered: 2,
      capacity: 500,
      installed: true,
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("chatty")).toBeInTheDocument());

    await user.selectOptions(
      screen.getByLabelText(/minimum level/i),
      "WARNING",
    );

    expect(screen.getByText("bad")).toBeInTheDocument();
    expect(screen.queryByText("chatty")).not.toBeInTheDocument();
  });

  it("clears the display buffer", async () => {
    const user = userEvent.setup();
    vi.mocked(client.tailLogs).mockResolvedValue({
      entries: [entry(1, "noise")],
      last_seq: 1,
      buffered: 1,
      capacity: 500,
      installed: true,
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("noise")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /clear/i }));

    expect(screen.queryByText("noise")).not.toBeInTheDocument();
  });

  it("shows an error banner and a disconnected indicator when the sidecar is down", async () => {
    vi.mocked(client.tailLogs).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "stream closed" },
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i),
    );
    expect(screen.getByTestId("console-connection")).toHaveTextContent(
      /not connected/i,
    );
  });
});
