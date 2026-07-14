import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import {
  useRegulatoryAssess,
  useRegulatoryChecklist,
  useRegulatoryGapAnalysis,
  useRegulatoryRoadmap,
  useRegulatoryStandards,
} from "@/hooks/useRegulatory";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";
import type { ProductProfile } from "@/api/types";

vi.mock("@/api/client");

const PRODUCT: ProductProfile = {
  product_name: "CardioRisk CDS",
  target_regions: ["us", "eu"],
  existing_artifacts: ["traceability_matrix"],
  uses_ai_ml: true,
};

describe("useRegulatoryStandards", () => {
  beforeEach(() => vi.resetAllMocks());

  it("lists the standards registry", async () => {
    vi.mocked(client.regulatoryStandards).mockResolvedValue({
      total: 1,
      standards: [
        {
          id: "iec_62304",
          name: "IEC 62304",
          region: "international",
          category: "software_lifecycle",
          reference: "IEC 62304:2006",
          requirements: ["Software development planning (5.1)"],
          required_artifacts: ["software_development_plan"],
        },
      ],
    });
    const { result } = renderHook(() => useRegulatoryStandards(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.standards[0].id).toBe("iec_62304");
  });
});

describe("useRegulatoryChecklist", () => {
  beforeEach(() => vi.resetAllMocks());

  it("fetches the checklist for a standard", async () => {
    vi.mocked(client.regulatoryChecklist).mockResolvedValue({
      standard_id: "iso_14971",
      standard_name: "ISO 14971",
      items: [],
      generated_at: "2026-07-13T00:00:00Z",
    });
    const { result } = renderHook(() => useRegulatoryChecklist("iso_14971"), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.regulatoryChecklist).toHaveBeenCalledWith("iso_14971");
  });

  it("does not fetch without a standard id", () => {
    renderHook(() => useRegulatoryChecklist(""), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    expect(client.regulatoryChecklist).not.toHaveBeenCalled();
  });
});

describe("useRegulatoryAssess", () => {
  beforeEach(() => vi.resetAllMocks());

  it("assesses a product profile", async () => {
    vi.mocked(client.regulatoryAssess).mockResolvedValue({
      product_name: "CardioRisk CDS",
      assessments: {},
      overall_score: 42.5,
      standards_assessed: 0,
      assessed_at: "2026-07-13T00:00:00Z",
    });
    const { result } = renderHook(() => useRegulatoryAssess(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ product: PRODUCT });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.regulatoryAssess).toHaveBeenCalledWith(PRODUCT, undefined);
    expect(result.current.data?.overall_score).toBe(42.5);
  });
});

describe("useRegulatoryGapAnalysis", () => {
  beforeEach(() => vi.resetAllMocks());

  it("runs a gap analysis for a standard", async () => {
    vi.mocked(client.regulatoryGapAnalysis).mockResolvedValue({
      standard_id: "iec_62304",
      standard_name: "IEC 62304",
      gaps: [],
      generated_at: "2026-07-13T00:00:00Z",
    });
    const { result } = renderHook(() => useRegulatoryGapAnalysis(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate({ product: PRODUCT, standard_id: "iec_62304" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.regulatoryGapAnalysis).toHaveBeenCalledWith(
      PRODUCT,
      "iec_62304",
    );
  });
});

describe("useRegulatoryRoadmap", () => {
  beforeEach(() => vi.resetAllMocks());

  it("generates a submission roadmap", async () => {
    vi.mocked(client.regulatoryRoadmap).mockResolvedValue({
      product_name: "CardioRisk CDS",
      target_regions: ["us", "eu"],
      phases: [],
      total_estimated_weeks: 0,
      generated_at: "2026-07-13T00:00:00Z",
    });
    const { result } = renderHook(() => useRegulatoryRoadmap(), {
      wrapper: wrapperWith(createTestQueryClient()),
    });
    result.current.mutate(PRODUCT);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(client.regulatoryRoadmap).toHaveBeenCalledWith(PRODUCT);
  });
});
