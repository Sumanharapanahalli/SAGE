import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Layout } from "@/components/layout/Layout";

describe("Layout", () => {
  it("renders sidebar, header, and outlet content", () => {
    render(
      <MemoryRouter initialEntries={["/approvals"]}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="approvals" element={<div>OUTLET_BODY</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByRole("heading")).toHaveTextContent(/approvals/i);
    expect(screen.getByText("OUTLET_BODY")).toBeInTheDocument();
  });
});
