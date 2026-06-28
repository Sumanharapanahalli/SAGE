import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CollectiveStats as StatsT } from "@/api/types";
import { CollectiveStats } from "@/components/domain/CollectiveStats";

const STATS: StatsT = {
  learning_count: 7,
  help_request_count: 2,
  help_requests_closed: 1,
  topics: { uart: 3, i2c: 2, spi: 2 },
  contributors: { medtech: 4, automotive: 3 },
  git_available: true,
  repo_path: "/tmp/collective",
};

describe("CollectiveStats", () => {
  it("renders the four counters and both histograms", () => {
    render(<CollectiveStats stats={STATS} />);
    expect(screen.getByText(/learnings/i)).toHaveTextContent("7");
    expect(screen.getByText(/open help/i)).toHaveTextContent("2");
    expect(screen.getByText(/closed help/i)).toHaveTextContent("1");
    expect(screen.getByText("uart")).toBeInTheDocument();
    expect(screen.getByText("medtech")).toBeInTheDocument();
  });

  it("shows an empty-state message when there are no learnings", () => {
    render(
      <CollectiveStats
        stats={{
          ...STATS,
          learning_count: 0,
          help_request_count: 0,
          help_requests_closed: 0,
          topics: {},
          contributors: {},
        }}
      />,
    );
    expect(screen.getByText(/no contributions yet/i)).toBeInTheDocument();
  });
});
