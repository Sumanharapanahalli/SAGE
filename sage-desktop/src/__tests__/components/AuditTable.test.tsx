import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuditTable } from "@/components/domain/AuditTable";
import type { AuditEvent } from "@/api/types";

const rows: AuditEvent[] = [
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
  {
    id: "e-2",
    timestamp: "2026-04-16T11:00:00Z",
    trace_id: null,
    event_type: "approval",
    status: null,
    actor: "system",
    action_type: "approved",
    input_context: null,
    output_content: null,
    metadata: {},
    approved_by: null,
    approver_role: null,
    approver_email: null,
    approver_provider: null,
  },
];

describe("AuditTable", () => {
  it("renders a row per event", () => {
    render(<AuditTable events={rows} />);
    expect(screen.getAllByRole("row")).toHaveLength(rows.length + 1); // + header
  });

  it("shows — for null trace_id", () => {
    render(<AuditTable events={rows} />);
    const e2row = screen.getByText(/approved/).closest("tr")!;
    expect(e2row).toHaveTextContent("—");
  });

  it("shows an empty-state message for zero events", () => {
    render(<AuditTable events={[]} />);
    expect(screen.getByText(/no audit events/i)).toBeInTheDocument();
  });
});
