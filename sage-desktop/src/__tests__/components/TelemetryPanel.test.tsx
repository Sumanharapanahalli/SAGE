import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  telemetryGetStatus: vi.fn(),
  telemetrySetEnabled: vi.fn(),
}));

import * as client from "@/api/client";
import { TelemetryPanel } from "@/components/domain/TelemetryPanel";

function renderPanel() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <TelemetryPanel />
    </QueryClientProvider>,
  );
}

describe("TelemetryPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the checkbox unchecked when disabled", async () => {
    vi.mocked(client.telemetryGetStatus).mockResolvedValue({
      enabled: false,
      anon_id: null,
      allowed_events: ["approval.decided"],
      allowed_fields: ["event", "status"],
    });
    renderPanel();
    const checkbox = await screen.findByRole("checkbox");
    expect(checkbox).not.toBeChecked();
    expect(screen.queryByText(/Anonymous ID/i)).not.toBeInTheDocument();
  });

  it("shows anon_id when enabled", async () => {
    vi.mocked(client.telemetryGetStatus).mockResolvedValue({
      enabled: true,
      anon_id: "uuid-1234",
      allowed_events: ["approval.decided"],
      allowed_fields: ["event"],
    });
    renderPanel();
    const checkbox = await screen.findByRole("checkbox");
    expect(checkbox).toBeChecked();
    expect(screen.getByText("uuid-1234")).toBeInTheDocument();
  });

  it("invokes set_enabled on toggle", async () => {
    vi.mocked(client.telemetryGetStatus).mockResolvedValue({
      enabled: false,
      anon_id: null,
      allowed_events: ["approval.decided"],
      allowed_fields: ["event"],
    });
    vi.mocked(client.telemetrySetEnabled).mockResolvedValue({
      enabled: true,
      anon_id: "new-uuid",
      allowed_events: ["approval.decided"],
      allowed_fields: ["event"],
    });
    renderPanel();
    const checkbox = await screen.findByRole("checkbox");
    await userEvent.click(checkbox);
    await waitFor(() =>
      expect(client.telemetrySetEnabled).toHaveBeenCalledWith(true),
    );
  });

  it("lists allowed events and fields inside the details disclosure", async () => {
    vi.mocked(client.telemetryGetStatus).mockResolvedValue({
      enabled: false,
      anon_id: null,
      allowed_events: ["approval.decided", "build.started"],
      allowed_fields: ["event", "status", "duration_ms"],
    });
    renderPanel();
    await screen.findByRole("checkbox");
    expect(screen.getByText(/approval\.decided, build\.started/)).toBeInTheDocument();
    expect(screen.getByText(/event, status, duration_ms/)).toBeInTheDocument();
  });
});
