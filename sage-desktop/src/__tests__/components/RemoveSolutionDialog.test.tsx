import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RemoveSolutionDialog } from "@/components/domain/RemoveSolutionDialog";
import type { SolutionRef } from "@/api/types";

const sol: SolutionRef = {
  name: "yoga",
  path: "/abs/yoga",
  has_sage_dir: true,
};

function renderDialog(onConfirm = vi.fn()) {
  render(
    <RemoveSolutionDialog
      solution={sol}
      isPending={false}
      error={null}
      onCancel={vi.fn()}
      onConfirm={onConfirm}
    />,
  );
  return onConfirm;
}

describe("RemoveSolutionDialog", () => {
  it("defaults to the non-destructive archive mode", () => {
    const onConfirm = renderDialog();
    fireEvent.click(screen.getByRole("button", { name: /^archive$/i }));
    expect(onConfirm).toHaveBeenCalledWith("archive", undefined);
  });

  it("does not ask for a typed confirmation to archive", () => {
    renderDialog();
    expect(
      screen.queryByLabelText(/type the solution name/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^archive$/i }),
    ).not.toBeDisabled();
  });

  it("blocks the delete until the exact name is typed", () => {
    const onConfirm = renderDialog();
    fireEvent.click(screen.getByRole("radio", { name: /delete permanently/i }));

    const btn = screen.getByRole("button", { name: /delete permanently/i });
    expect(btn).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/type the solution name/i), {
      target: { value: "Yoga" },
    });
    expect(btn).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/type the solution name/i), {
      target: { value: "yoga" },
    });
    expect(btn).not.toBeDisabled();

    fireEvent.click(btn);
    expect(onConfirm).toHaveBeenCalledWith("delete", "yoga");
  });

  it("surfaces a failed removal", () => {
    render(
      <RemoveSolutionDialog
        solution={sol}
        isPending={false}
        error={{ kind: "SidecarDown", detail: { message: "dead" } }}
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/remove failed/i);
  });

  it("calls onCancel without removing anything", () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(
      <RemoveSolutionDialog
        solution={sol}
        isPending={false}
        error={null}
        onCancel={onCancel}
        onConfirm={onConfirm}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onCancel).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });
});
