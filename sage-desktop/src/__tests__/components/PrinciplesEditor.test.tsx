import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { ConstitutionPrinciple } from "@/api/types";
import { PrinciplesEditor } from "@/components/domain/PrinciplesEditor";

const P: ConstitutionPrinciple[] = [
  { id: "p1", text: "Test first", weight: 0.8 },
  { id: "p2", text: "Ship small", weight: 1.0 },
];

describe("PrinciplesEditor", () => {
  it("renders every principle with its id, text, and weight", () => {
    render(<PrinciplesEditor principles={P} onChange={() => {}} />);
    expect(screen.getByLabelText("principle 1 id")).toHaveValue("p1");
    expect(screen.getByLabelText("principle 1 text")).toHaveValue("Test first");
    expect(screen.getByLabelText("principle 2 weight")).toHaveValue(1);
  });

  it("emits an updated list when text is edited", () => {
    const spy = vi.fn();
    render(<PrinciplesEditor principles={P} onChange={spy} />);
    fireEvent.change(screen.getByLabelText("principle 1 text"), {
      target: { value: "Test first, always" },
    });
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0][0].text).toBe("Test first, always");
  });

  it("clamps weight into [0, 1]", () => {
    const spy = vi.fn();
    render(<PrinciplesEditor principles={P} onChange={spy} />);
    fireEvent.change(screen.getByLabelText("principle 1 weight"), {
      target: { value: "9" },
    });
    expect(spy.mock.calls[0][0][0].weight).toBe(1);
  });

  it("removes a principle when the remove button is clicked", () => {
    const spy = vi.fn();
    render(<PrinciplesEditor principles={P} onChange={spy} />);
    fireEvent.click(screen.getByLabelText("remove principle 2"));
    expect(spy.mock.calls[0][0]).toHaveLength(1);
    expect(spy.mock.calls[0][0][0].id).toBe("p1");
  });

  it("adds a new principle with a generated id on + Add", () => {
    const spy = vi.fn();
    render(<PrinciplesEditor principles={P} onChange={spy} />);
    fireEvent.click(screen.getByRole("button", { name: /add principle/i }));
    const next = spy.mock.calls[0][0];
    expect(next).toHaveLength(3);
    expect(next[2].id).toBe("p3");
  });
});
