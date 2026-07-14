import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  regulatoryStandards: vi.fn(),
  regulatoryChecklist: vi.fn(),
  regulatoryAssess: vi.fn(),
  regulatoryGapAnalysis: vi.fn(),
  regulatoryRoadmap: vi.fn(),
}));

import * as client from "@/api/client";
import Regulatory from "@/pages/Regulatory";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

const STANDARDS = {
  total: 1,
  standards: [
    {
      id: "iec_62304",
      name: "IEC 62304 — Medical Device Software Lifecycle",
      region: "international",
      category: "software_lifecycle",
      reference: "IEC 62304:2006",
      requirements: ["Software development planning (5.1)"],
      required_artifacts: ["software_development_plan"],
    },
  ],
};

const CHECKLIST = {
  standard_id: "iec_62304",
  standard_name: "IEC 62304 — Medical Device Software Lifecycle",
  items: [
    {
      id: "iec_62304-001",
      requirement: "Software development planning (5.1)",
      description: "Verify compliance with: Software development planning",
      evidence_needed: ["software_development_plan"],
      checked: false,
    },
  ],
  generated_at: "2026-07-13T00:00:00Z",
};

function renderPage() {
  return render(<Regulatory />, {
    wrapper: wrapperWith(createTestQueryClient()),
  });
}

describe("Regulatory page", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.regulatoryStandards).mockResolvedValue(STANDARDS);
    vi.mocked(client.regulatoryChecklist).mockResolvedValue(CHECKLIST);
  });

  it("loads the registry and the first standard's checklist", async () => {
    renderPage();
    await waitFor(() =>
      expect(client.regulatoryChecklist).toHaveBeenCalledWith("iec_62304"),
    );
    expect(
      await screen.findByText(/Software development planning/i),
    ).toBeInTheDocument();
  });

  it("shows a loading indicator while the registry loads", () => {
    vi.mocked(client.regulatoryStandards).mockReturnValue(
      new Promise(() => {}),
    );
    renderPage();
    expect(screen.getByText(/loading standards/i)).toBeInTheDocument();
  });

  it("assesses the typed product profile", async () => {
    vi.mocked(client.regulatoryAssess).mockResolvedValue({
      product_name: "CardioRisk",
      assessments: {
        iec_62304: {
          standard_id: "iec_62304",
          standard_name: "IEC 62304",
          region: "international",
          compliance_score: 61.5,
          met_requirements: [],
          gaps: [],
          required_artifacts: ["soup_inventory"],
          met_artifacts: [],
          missing_artifacts: ["soup_inventory"],
        },
      },
      overall_score: 61.5,
      standards_assessed: 1,
      assessed_at: "2026-07-13T00:00:00Z",
    });
    renderPage();
    await screen.findByRole("combobox");

    await userEvent.type(
      screen.getByLabelText(/product name/i),
      "CardioRisk",
    );
    await userEvent.click(
      screen.getByRole("button", { name: /assess compliance/i }),
    );

    await waitFor(() =>
      expect(client.regulatoryAssess).toHaveBeenCalledWith(
        expect.objectContaining({
          product_name: "CardioRisk",
          target_regions: ["us", "eu"],
        }),
        undefined,
      ),
    );
    expect(await screen.findByText(/61.5% across/i)).toBeInTheDocument();
    expect(await screen.findByText(/soup_inventory/)).toBeInTheDocument();
  });

  it("runs a gap analysis for the selected standard", async () => {
    vi.mocked(client.regulatoryGapAnalysis).mockResolvedValue({
      standard_id: "iec_62304",
      standard_name: "IEC 62304",
      gaps: [
        {
          requirement: "SOUP management (7.1)",
          status: "missing",
          remediation: "Create documentation for: SOUP management",
          priority: "medium",
        },
      ],
      generated_at: "2026-07-13T00:00:00Z",
    });
    renderPage();
    await screen.findByRole("combobox");

    await userEvent.click(screen.getByRole("button", { name: /gap analysis/i }));
    await waitFor(() =>
      expect(client.regulatoryGapAnalysis).toHaveBeenCalledWith(
        expect.objectContaining({ target_regions: ["us", "eu"] }),
        "iec_62304",
      ),
    );
    // The requirement text also appears inside its remediation string.
    expect((await screen.findAllByText(/SOUP management/)).length).toBeGreaterThan(0);
    expect(screen.getByText("missing")).toBeInTheDocument();
  });

  it("generates a submission roadmap", async () => {
    vi.mocked(client.regulatoryRoadmap).mockResolvedValue({
      product_name: "CardioRisk",
      target_regions: ["us", "eu"],
      phases: [
        {
          phase_name: "Phase 1: Foundation",
          description: "Core lifecycle and risk management",
          standards: ["iec_62304"],
          deliverables: ["Software Development Plan"],
          estimated_weeks: 4,
        },
      ],
      total_estimated_weeks: 4,
      generated_at: "2026-07-13T00:00:00Z",
    });
    renderPage();
    await screen.findByRole("combobox");

    await userEvent.click(
      screen.getByRole("button", { name: /submission roadmap/i }),
    );
    await waitFor(() => expect(client.regulatoryRoadmap).toHaveBeenCalled());
    expect(await screen.findByText(/Phase 1: Foundation/)).toBeInTheDocument();
    // "4 weeks" shows in both the roadmap total and the phase heading.
    expect(screen.getAllByText(/4 weeks/).length).toBeGreaterThan(0);
    expect(
      screen.getByText(/Software Development Plan/),
    ).toBeInTheDocument();
  });

  it("shows an error banner when the registry fails", async () => {
    vi.mocked(client.regulatoryStandards).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "registry dead" },
    });
    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/registry dead/i),
    );
  });
});
