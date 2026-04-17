import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  checkUpdate: vi.fn(),
  installUpdate: vi.fn(),
}));

import * as client from "@/api/client";
import { UpdatePanel } from "@/components/domain/UpdatePanel";

function renderPanel() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <UpdatePanel />
    </QueryClientProvider>,
  );
}

describe("UpdatePanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders the check button idle", () => {
    renderPanel();
    expect(screen.getByRole("button", { name: /check for updates/i })).toBeEnabled();
  });

  it("shows up-to-date message after click", async () => {
    vi.mocked(client.checkUpdate).mockResolvedValue({
      kind: "UpToDate",
      current_version: "0.1.0",
    });
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /check for updates/i }));
    await waitFor(() =>
      expect(screen.getByText(/you're on the latest version/i)).toBeInTheDocument(),
    );
  });

  it("shows available version + install button", async () => {
    vi.mocked(client.checkUpdate).mockResolvedValue({
      kind: "Available",
      current_version: "0.1.0",
      new_version: "0.2.0",
      notes: "release notes here",
    });
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /check for updates/i }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /download & restart/i })).toBeInTheDocument(),
    );
    expect(screen.getByText(/0\.2\.0/)).toBeInTheDocument();
    expect(screen.getByText(/release notes here/)).toBeInTheDocument();
  });

  it("surfaces updater error kind", async () => {
    vi.mocked(client.checkUpdate).mockResolvedValue({
      kind: "Error",
      detail: "network timeout",
    });
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: /check for updates/i }));
    await waitFor(() =>
      expect(screen.getByText(/updater error: network timeout/i)).toBeInTheDocument(),
    );
  });
});
