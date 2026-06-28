import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentCard } from "@/components/domain/AgentCard";
import type { Agent } from "@/api/types";

const core: Agent = {
  name: "analyst",
  kind: "core",
  description: "Analyzes signals and surfaces insights.",
  system_prompt: "You are an analyst.",
  event_count: 7,
  last_active: "2026-04-16T10:00:00Z",
};

describe("AgentCard", () => {
  it("shows name, kind badge, and event count", () => {
    render(<AgentCard agent={core} />);
    expect(screen.getByText(/analyst/i)).toBeInTheDocument();
    expect(screen.getByText(/core/i)).toBeInTheDocument();
    expect(screen.getByText(/7/)).toBeInTheDocument();
  });

  it("renders 'never' when last_active is null", () => {
    render(
      <AgentCard
        agent={{ ...core, last_active: null, event_count: 0 }}
      />,
    );
    expect(screen.getByText(/never/i)).toBeInTheDocument();
  });

  it("shows the custom badge for custom agents", () => {
    render(<AgentCard agent={{ ...core, kind: "custom" }} />);
    expect(screen.getByText(/custom/i)).toBeInTheDocument();
  });
});
