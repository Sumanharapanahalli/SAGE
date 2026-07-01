import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import {
  useComplianceDomains,
  useComplianceChecklist,
  useAssessComplianceGap,
} from "@/hooks/useCompliance";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useComplianceDomains", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists compliance domains", async () => {
    vi.mocked(client.listComplianceDomains).mockResolvedValue({
      domains: [{ domain: "medtech", standard: "IEC 62304", description: "", authority: "", risk_levels: ["CLASS_C"], hil_required_for: [] }],
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useComplianceDomains(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.domains[0].domain).toBe("medtech");
  });
});

describe("useComplianceChecklist", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches a checklist for the given domain and risk level", async () => {
    vi.mocked(client.getComplianceChecklist).mockResolvedValue({
      domain: "medtech", risk_level: "CLASS_C", standard: "", description: "",
      authority: "", hil_testing_required: false, total_items: 0, flags: 0,
      required_tasks: 0, artifacts: 0, items: [],
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(
      () => useComplianceChecklist("medtech", "CLASS_C"),
      { wrapper: wrapperWith(qc) },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.getComplianceChecklist).toHaveBeenCalledWith("medtech", "CLASS_C");
  });

  it("does not fetch when domain is empty", () => {
    const qc = createTestQueryClient();
    renderHook(() => useComplianceChecklist("", "CLASS_C"), {
      wrapper: wrapperWith(qc),
    });
    expect(client.getComplianceChecklist).not.toHaveBeenCalled();
  });
});

describe("useAssessComplianceGap", () => {
  beforeEach(() => vi.resetAllMocks());

  it("runs a gap assessment with the given completed tasks", async () => {
    vi.mocked(client.assessComplianceGap).mockResolvedValue({
      domain: "medtech", risk_level: "CLASS_C", required_tasks: ["RISK_ANALYSIS"],
      completed_tasks: [], missing_tasks: ["RISK_ANALYSIS"], hil_tasks_missing: [],
      compliance_pct: 0, compliant: false, blocking_gaps: [],
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useAssessComplianceGap(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ domain: "medtech", risk_level: "CLASS_C", completed_tasks: [] });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.compliance_pct).toBe(0);
  });
});
