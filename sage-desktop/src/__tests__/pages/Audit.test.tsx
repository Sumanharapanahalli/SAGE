import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  listAuditEvents: vi.fn(),
  getAuditByTrace: vi.fn(),
  auditStats: vi.fn(),
}));

import * as client from "@/api/client";
import { Audit } from "@/pages/Audit";
import {
  createTestQueryClient,
  wrapperWith,
} from "../helpers/queryWrapper";

describe("Audit page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders table rows", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 1,
      limit: 50,
      offset: 0,
      events: [
        {
          id: "e-1",
          timestamp: "2026-04-16T10:00:00Z",
          trace_id: "t-1",
          event_type: "analysis",
          status: null,
          actor: "analyst",
          action_type: "yaml_edit",
          input_context: null,
          output_content: null,
          metadata: {},
          approved_by: null,
          approver_role: null,
          approver_email: null,
          approver_provider: null,
        },
      ],
    });
    render(<Audit />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/yaml_edit/)).toBeInTheDocument(),
    );
  });

  it("shows empty state", async () => {
    vi.mocked(client.listAuditEvents).mockResolvedValue({
      total: 0,
      limit: 50,
      offset: 0,
      events: [],
    });
    render(<Audit />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/no audit events/i)).toBeInTheDocument(),
    );
  });
});
