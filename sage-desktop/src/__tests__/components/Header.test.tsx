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
});
