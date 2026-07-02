import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Header } from "@/components/layout/Header";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Header />
    </MemoryRouter>,
  );
}

describe("Header", () => {
  it("shows the route title for known routes", () => {
    renderAt("/approvals");
    expect(screen.getByRole("heading")).toHaveTextContent(/approvals/i);
  });

  it("falls back to SAGE Desktop for unknown routes", () => {
    renderAt("/somewhere/unknown");
    expect(screen.getByRole("heading")).toHaveTextContent(/sage desktop/i);
  });

  it.each([
    ["/analyze", /analyze/i],
    ["/home", /solutions/i],
    ["/compliance", /compliance/i],
    ["/costs", /costs/i],
    ["/workflows", /workflows/i],
    ["/skills", /skills/i],
    ["/organization", /organization/i],
    ["/monitor", /monitor/i],
    ["/goals", /goals/i],
    ["/eval", /eval/i],
    ["/hil", /hardware-in-the-loop/i],
  ])("shows a real title for %s (not the generic fallback)", (path, re) => {
    renderAt(path);
    const heading = screen.getByRole("heading");
    expect(heading).toHaveTextContent(re);
    expect(heading).not.toHaveTextContent(/sage desktop/i);
  });
});
