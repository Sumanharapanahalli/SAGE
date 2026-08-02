import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import Safety from "@/pages/Safety";

import { createTestQueryClient } from "../helpers/queryWrapper";

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    runFmea: vi.fn(),
    runFta: vi.fn(),
    classifyAsil: vi.fn(),
    classifySil: vi.fn(),
    classifyIec62304: vi.fn(),
  };
});

function renderPage() {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <Safety />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// Regexes are anchored: an unanchored /sil/i matches BOTH the "ASIL" and
// "SIL" tabs, which makes getByRole throw on multiple matches.
async function switchTo(user: ReturnType<typeof userEvent.setup>, name: RegExp) {
  await user.click(screen.getByRole("tab", { name }));
}

describe("Safety page", () => {
  beforeEach(() => vi.resetAllMocks());

  // ── Nothing auto-fires ──────────────────────────────────────────────────

  it("does not run any analysis on mount", () => {
    renderPage();
    expect(client.runFmea).not.toHaveBeenCalled();
    expect(client.runFta).not.toHaveBeenCalled();
    expect(client.classifyAsil).not.toHaveBeenCalled();
    expect(client.classifySil).not.toHaveBeenCalled();
    expect(client.classifyIec62304).not.toHaveBeenCalled();
  });

  // ── FMEA ────────────────────────────────────────────────────────────────

  it("runs FMEA with the entered row and shows the RPN", async () => {
    vi.mocked(client.runFmea).mockResolvedValue({
      entries: [
        {
          id: "FMEA-ABC123",
          component: "pump",
          failure_mode: "stall",
          effect: "no flow",
          severity: 9,
          occurrence: 7,
          detection: 6,
          rpn: 378,
          risk_level: "critical",
          action_required: true,
        },
      ],
      summary: {
        total_entries: 1,
        critical_count: 1,
        high_count: 0,
        max_rpn: 378,
        action_items: 1,
      },
      generated_at: "2026-07-31T00:00:00Z",
    });
    const user = userEvent.setup();
    renderPage();

    await user.type(screen.getByLabelText(/component/i), "pump");
    await user.type(screen.getByLabelText(/failure mode/i), "stall");
    await user.type(screen.getByLabelText(/effect/i), "no flow");
    await user.click(screen.getByRole("button", { name: /run fmea/i }));

    await waitFor(() =>
      expect(client.runFmea).toHaveBeenCalledWith([
        expect.objectContaining({
          component: "pump",
          failure_mode: "stall",
          effect: "no flow",
        }),
      ]),
    );
    await waitFor(() => expect(screen.getByText("378")).toBeInTheDocument());
    expect(screen.getByText(/critical/i)).toBeInTheDocument();
  });

  // ── FTA ─────────────────────────────────────────────────────────────────

  it("sends a NESTED fault tree, not a flat gate list", async () => {
    // Regression guard: the web page posts {top_event, gates: [...]}, a shape
    // calculate_fta() cannot walk — it silently yields probability 0.0 and no
    // cut sets. Desktop must send {top_event, gate, children:[...]}.
    vi.mocked(client.runFta).mockResolvedValue({
      top_event: "loss of infusion",
      probability: 0.003,
      minimal_cut_sets: [["pump stall"], ["power loss"]],
      single_point_failures: [["pump stall"], ["power loss"]],
      generated_at: "2026-07-31T00:00:00Z",
    });
    const user = userEvent.setup();
    renderPage();
    await switchTo(user, /fta/i);

    await user.type(screen.getByLabelText(/top event/i), "loss of infusion");
    await user.type(screen.getByLabelText(/^event/i), "pump stall");
    await user.click(screen.getByRole("button", { name: /run fta/i }));

    await waitFor(() => expect(client.runFta).toHaveBeenCalled());
    const tree = vi.mocked(client.runFta).mock.calls[0][0];
    expect(tree).toMatchObject({
      top_event: "loss of infusion",
      gate: expect.stringMatching(/^(AND|OR)$/),
    });
    expect(Array.isArray(tree.children)).toBe(true);
    expect(tree).not.toHaveProperty("gates");
    // Each leaf must carry BOTH keys or one of the two results degrades.
    expect(tree.children?.[0]).toMatchObject({
      event: "pump stall",
      probability: expect.any(Number),
    });

    await waitFor(() =>
      expect(screen.getByText(/single-point failure/i)).toBeInTheDocument(),
    );
  });

  // ── ASIL / SIL / IEC 62304: the real engine field names ──────────────────

  it("renders the ASIL from `asil` (the engine's real field)", async () => {
    vi.mocked(client.classifyAsil).mockResolvedValue({
      asil: "D",
      severity: "S3",
      exposure: "E4",
      controllability: "C3",
      description: "Highest integrity level",
      standard: "ISO 26262",
    });
    const user = userEvent.setup();
    renderPage();
    await switchTo(user, /^asil/i);
    await user.click(screen.getByRole("button", { name: /classify asil/i }));

    await waitFor(() =>
      expect(client.classifyAsil).toHaveBeenCalledWith("S3", "E4", "C3"),
    );
    await waitFor(() =>
      expect(screen.getByTestId("asil-result")).toHaveTextContent("D"),
    );
    expect(screen.getByText(/highest integrity level/i)).toBeInTheDocument();
  });

  it("renders the SIL from `sil` (the engine's real field)", async () => {
    vi.mocked(client.classifySil).mockResolvedValue({
      sil: 4,
      pfh: 1e-8,
      description: "Very high integrity",
      standard: "IEC 61508",
    });
    const user = userEvent.setup();
    renderPage();
    await switchTo(user, /^sil/i);
    await user.click(screen.getByRole("button", { name: /classify sil/i }));

    await waitFor(() => expect(client.classifySil).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByTestId("sil-result")).toHaveTextContent("4"),
    );
  });

  it("renders IEC 62304 class and required_processes", async () => {
    vi.mocked(client.classifyIec62304).mockResolvedValue({
      safety_class: "C",
      description: "Death or serious injury possible",
      required_processes: ["software_risk_management", "unit_verification"],
      standard: "IEC 62304:2006/AMD1:2015",
    });
    const user = userEvent.setup();
    renderPage();
    await switchTo(user, /62304/i);
    await user.click(screen.getByRole("button", { name: /classify/i }));

    await waitFor(() => expect(client.classifyIec62304).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByTestId("iec62304-result")).toHaveTextContent("C"),
    );
    expect(screen.getByText(/software_risk_management/i)).toBeInTheDocument();
  });

  // ── Errors ──────────────────────────────────────────────────────────────

  it("shows an error banner when an analysis fails", async () => {
    vi.mocked(client.classifySil).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "pfh must be >= 0" },
    });
    const user = userEvent.setup();
    renderPage();
    await switchTo(user, /^sil/i);
    await user.click(screen.getByRole("button", { name: /classify sil/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/pfh must be >= 0/i),
    );
  });
});
