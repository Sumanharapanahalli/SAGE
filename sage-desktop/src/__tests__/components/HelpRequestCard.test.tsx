import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { HelpRequest } from "@/api/types";
import { HelpRequestCard } from "@/components/domain/HelpRequestCard";

const OPEN: HelpRequest = {
  id: "hr-123",
  title: "I2C bus recovery help",
  requester_agent: "developer",
  requester_solution: "automotive",
  status: "open",
  urgency: "high",
  required_expertise: ["i2c", "stm32"],
  context: "Stuck on TASK-456.",
  created_at: "2026-04-17T00:00:00+00:00",
  claimed_by: null,
  responses: [],
  resolved_at: null,
};

describe("HelpRequestCard", () => {
  it("renders title, urgency, expertise, and requester", () => {
    render(
      <HelpRequestCard
        request={OPEN}
        onClaim={() => {}}
        onRespond={() => {}}
        onClose={() => {}}
      />,
    );
    expect(
      screen.getByText("I2C bus recovery help"),
    ).toBeInTheDocument();
    expect(screen.getByText(/high/i)).toBeInTheDocument();
    expect(screen.getByText("i2c")).toBeInTheDocument();
    expect(screen.getByText(/developer/)).toBeInTheDocument();
  });

  it("invokes onClaim with the request id", () => {
    const spy = vi.fn();
    render(
      <HelpRequestCard
        request={OPEN}
        onClaim={spy}
        onRespond={() => {}}
        onClose={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^claim$/i }));
    expect(spy).toHaveBeenCalledWith("hr-123");
  });

  it("requires confirm click before invoking onClose", () => {
    const spy = vi.fn();
    render(
      <HelpRequestCard
        request={OPEN}
        onClaim={() => {}}
        onRespond={() => {}}
        onClose={spy}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^close$/i }));
    expect(spy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /confirm/i }));
    expect(spy).toHaveBeenCalledWith("hr-123");
  });
});
