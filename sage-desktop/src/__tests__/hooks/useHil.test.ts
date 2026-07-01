import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import { useHilStatus, useHilConnect, useHilRunSuite, useHilReport } from "@/hooks/useHil";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

vi.mock("@/api/client");

describe("useHilStatus", () => {
  beforeEach(() => vi.resetAllMocks());

  it("reads HIL status", async () => {
    vi.mocked(client.getHilStatus).mockResolvedValue({
      connected: false,
      transport: "none",
      session_id: null,
      tests_run: 0,
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useHilStatus(), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.connected).toBe(false);
  });
});

describe("useHilConnect", () => {
  beforeEach(() => vi.resetAllMocks());

  it("connects and invalidates HIL status", async () => {
    vi.mocked(client.hilConnect).mockResolvedValue({
      transport: "mock",
      connected: true,
      session_id: "hil_1",
      message: "Connected",
    });
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useHilConnect(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ transport: "mock" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.hilConnect).toHaveBeenCalledWith("mock", undefined);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["hilStatus"] });
  });
});

describe("useHilRunSuite", () => {
  beforeEach(() => vi.resetAllMocks());

  it("runs a suite and invalidates HIL status", async () => {
    vi.mocked(client.hilRunSuite).mockResolvedValue({
      session_id: "hil_1",
      transport: "mock",
      total: 1,
      passed: 1,
      failed: 0,
      errors: 0,
      skipped: 0,
      blocked: 0,
      pass_rate: 100,
      results: [],
    });
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useHilRunSuite(), {
      wrapper: wrapperWith(qc),
    });
    result.current.mutate({ tests: [{ id: "TC-1", name: "t", requirement_id: "R1" }] });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["hilStatus"] });
  });
});

describe("useHilReport", () => {
  beforeEach(() => vi.resetAllMocks());

  it("is disabled until sessionId is provided", () => {
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useHilReport(""), {
      wrapper: wrapperWith(qc),
    });
    expect(result.current.fetchStatus).toBe("idle");
    expect(client.hilReport).not.toHaveBeenCalled();
  });

  it("fetches a report once enabled", async () => {
    vi.mocked(client.hilReport).mockResolvedValue({
      report_type: "HIL Test Evidence — IEC62304",
      standard: "IEC62304",
      standard_full_name: "IEC 62304",
      generated_at: "",
      session_id: "hil_1",
      transport: "mock",
      evidence_sections: [],
      pass_criteria: "",
      summary: {
        total_tests: 1, passed: 1, failed: 0, blocked: 0,
        pass_rate: 100, overall_status: "PASS",
      },
      traceability: [],
      deviations: [],
      failed_tests: [],
    });
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useHilReport("hil_1"), {
      wrapper: wrapperWith(qc),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.hilReport).toHaveBeenCalledWith("hil_1", undefined);
  });
});
