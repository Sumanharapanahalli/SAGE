import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";

import { sidecarStatusKey } from "@/hooks/useSidecarStatus";
import { SidecarStatusBanner } from "@/components/layout/SidecarStatusBanner";
import { createTestQueryClient } from "../helpers/queryWrapper";

describe("SidecarStatusBanner", () => {
  it("renders nothing when the sidecar is online", () => {
    const qc = createTestQueryClient();
    render(
      <QueryClientProvider client={qc}>
        <SidecarStatusBanner />
      </QueryClientProvider>,
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows a reconnecting banner while the sidecar is recovering", () => {
    const qc = createTestQueryClient();
    qc.setQueryData(sidecarStatusKey, {
      online: false,
      reason: "sidecar exited unexpectedly",
    });
    render(
      <QueryClientProvider client={qc}>
        <SidecarStatusBanner />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/reconnect/i);
  });

  it("shows a terminal banner when recovery is exhausted", () => {
    const qc = createTestQueryClient();
    qc.setQueryData(sidecarStatusKey, {
      online: false,
      reason: "recovery exhausted",
      exhausted: true,
    });
    render(
      <QueryClientProvider client={qc}>
        <SidecarStatusBanner />
      </QueryClientProvider>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/restart|switch/i);
  });
});
