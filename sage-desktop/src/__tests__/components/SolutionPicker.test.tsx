import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SolutionPicker } from "@/components/domain/SolutionPicker";
import type { SolutionRef } from "@/api/types";

const SOLUTIONS: SolutionRef[] = [
  { name: "meditation_app", path: "/abs/meditation_app", has_sage_dir: true },
  { name: "yoga", path: "/abs/yoga", has_sage_dir: false },
];

describe("SolutionPicker", () => {
  it("shows a loading hint while solutions load", () => {
    render(
      <SolutionPicker
        solutions={[]}
        current={null}
        isLoading={true}
        isSwitching={false}
        switchError={null}
        onSwitch={() => {}}
      />,
    );
    expect(screen.getByText(/loading solutions/i)).toBeInTheDocument();
  });

  it("shows an empty-state when no solutions exist", () => {
    render(
      <SolutionPicker
        solutions={[]}
        current={null}
        isLoading={false}
        isSwitching={false}
        switchError={null}
        onSwitch={() => {}}
      />,
    );
    expect(screen.getByText(/no solutions found/i)).toBeInTheDocument();
  });

  it("renders every solution in the dropdown with the current one selected", () => {
    render(
      <SolutionPicker
        solutions={SOLUTIONS}
        current={{ name: "meditation_app", path: "/abs/meditation_app" }}
        isLoading={false}
        isSwitching={false}
        switchError={null}
        onSwitch={() => {}}
      />,
    );
    const select = screen.getByLabelText(/active solution/i) as HTMLSelectElement;
    expect(select.value).toBe("meditation_app");
    expect(screen.getByRole("option", { name: /meditation_app/i })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: /yoga \(new\)/i })).toBeInTheDocument();
  });

  it("calls onSwitch with the chosen solution when the user picks a new one", () => {
    const spy = vi.fn();
    render(
      <SolutionPicker
        solutions={SOLUTIONS}
        current={{ name: "meditation_app", path: "/abs/meditation_app" }}
        isLoading={false}
        isSwitching={false}
        switchError={null}
        onSwitch={spy}
      />,
    );
    fireEvent.change(screen.getByLabelText(/active solution/i), {
      target: { value: "yoga" },
    });
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0]).toEqual(SOLUTIONS[1]);
  });

  it("does not call onSwitch when user re-selects the current solution", () => {
    const spy = vi.fn();
    render(
      <SolutionPicker
        solutions={SOLUTIONS}
        current={{ name: "meditation_app", path: "/abs/meditation_app" }}
        isLoading={false}
        isSwitching={false}
        switchError={null}
        onSwitch={spy}
      />,
    );
    fireEvent.change(screen.getByLabelText(/active solution/i), {
      target: { value: "meditation_app" },
    });
    expect(spy).not.toHaveBeenCalled();
  });

  it("disables the select and shows a status message while switching", () => {
    render(
      <SolutionPicker
        solutions={SOLUTIONS}
        current={{ name: "meditation_app", path: "/abs/meditation_app" }}
        isLoading={false}
        isSwitching={true}
        switchError={null}
        onSwitch={() => {}}
      />,
    );
    expect(screen.getByLabelText(/active solution/i)).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/switching/i);
  });

  it("renders a typed error when the switch fails", () => {
    render(
      <SolutionPicker
        solutions={SOLUTIONS}
        current={{ name: "meditation_app", path: "/abs/meditation_app" }}
        isLoading={false}
        isSwitching={false}
        switchError={{ kind: "SolutionNotFound", detail: { name: "ghost" } }}
        onSwitch={() => {}}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/solution not found: ghost/i);
  });
});
