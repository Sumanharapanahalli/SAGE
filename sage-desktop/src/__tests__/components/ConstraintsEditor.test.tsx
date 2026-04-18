import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConstraintsEditor } from "@/components/domain/ConstraintsEditor";

describe("ConstraintsEditor", () => {
  it("renders one input per constraint", () => {
    render(
      <ConstraintsEditor
        constraints={["No /prod/", "No secrets"]}
        onChange={() => {}}
      />,
    );
    expect(screen.getByLabelText("constraint 1")).toHaveValue("No /prod/");
    expect(screen.getByLabelText("constraint 2")).toHaveValue("No secrets");
  });

  it("emits an updated list when a constraint is edited", () => {
    const spy = vi.fn();
    render(<ConstraintsEditor constraints={["No /prod/"]} onChange={spy} />);
    fireEvent.change(screen.getByLabelText("constraint 1"), {
      target: { value: "No /prod/ writes" },
    });
    expect(spy).toHaveBeenCalledWith(["No /prod/ writes"]);
  });

  it("removes a constraint when remove is clicked", () => {
    const spy = vi.fn();
    render(
      <ConstraintsEditor constraints={["a", "b", "c"]} onChange={spy} />,
    );
    fireEvent.click(screen.getByLabelText("remove constraint 2"));
    expect(spy).toHaveBeenCalledWith(["a", "c"]);
  });

  it("adds a blank constraint on + Add", () => {
    const spy = vi.fn();
    render(<ConstraintsEditor constraints={["a"]} onChange={spy} />);
    fireEvent.click(screen.getByRole("button", { name: /add constraint/i }));
    expect(spy).toHaveBeenCalledWith(["a", ""]);
  });
});
