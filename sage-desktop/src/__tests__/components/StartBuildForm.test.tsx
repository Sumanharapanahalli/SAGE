import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StartBuildForm } from "@/components/domain/StartBuildForm";

describe("StartBuildForm", () => {
  it("disables Start until product_description meets the minimum", () => {
    render(
      <StartBuildForm
        isPending={false}
        error={null}
        onStart={vi.fn()}
      />,
    );
    const btn = screen.getByRole("button", { name: /start build/i });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/product description/i), {
      target: { value: "short" },
    });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/product description/i), {
      target: { value: "x".repeat(30) },
    });
    expect(btn).not.toBeDisabled();
  });

  it("forwards trimmed params with defaults", () => {
    const onStart = vi.fn();
    render(
      <StartBuildForm isPending={false} error={null} onStart={onStart} />,
    );
    fireEvent.change(screen.getByLabelText(/product description/i), {
      target: { value: "  yoga app with 10-min sessions and audio guides  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /start build/i }));
    expect(onStart).toHaveBeenCalledWith({
      product_description:
        "yoga app with 10-min sessions and audio guides",
      solution_name: "",
      repo_url: "",
      workspace_dir: "",
      critic_threshold: 70,
      hitl_level: "standard",
    });
  });

  it("renders a typed error banner", () => {
    render(
      <StartBuildForm
        isPending={false}
        error={{ kind: "SidecarDown", detail: { message: "decomposer" } }}
        onStart={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/SidecarDown/);
  });
});
