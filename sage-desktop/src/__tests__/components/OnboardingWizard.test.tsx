import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnboardingWizard } from "@/components/domain/OnboardingWizard";

describe("OnboardingWizard", () => {
  it("disables Generate until name + description are valid", () => {
    render(
      <OnboardingWizard
        isPending={false}
        error={null}
        result={null}
        onGenerate={vi.fn()}
        onSwitch={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /generate/i })).toBeDisabled();
  });

  it("rejects names with spaces or caps", () => {
    render(
      <OnboardingWizard
        isPending={false}
        error={null}
        result={null}
        onGenerate={vi.fn()}
        onSwitch={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/solution name/i), {
      target: { value: "Bad Name" },
    });
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "x".repeat(40) },
    });
    expect(screen.getByRole("button", { name: /generate/i })).toBeDisabled();
    expect(screen.getByText(/snake_case/i)).toBeInTheDocument();
  });

  it("calls onGenerate with trimmed params", () => {
    const onGenerate = vi.fn();
    render(
      <OnboardingWizard
        isPending={false}
        error={null}
        result={null}
        onGenerate={onGenerate}
        onSwitch={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/solution name/i), {
      target: { value: "yoga" },
    });
    fireEvent.change(screen.getByLabelText(/description/i), {
      target: { value: "yoga instructor assistant with thirty chars plus" },
    });
    fireEvent.click(screen.getByRole("button", { name: /generate/i }));
    expect(onGenerate).toHaveBeenCalledWith(
      expect.objectContaining({ solution_name: "yoga" }),
    );
  });

  it("shows a 'Switch to it' button on created success", () => {
    const onSwitch = vi.fn();
    render(
      <OnboardingWizard
        isPending={false}
        error={null}
        result={{
          solution_name: "yoga",
          path: "/abs/yoga",
          status: "created",
          files: { "project.yaml": "x" },
          suggested_routes: [],
          message: "ok",
        }}
        onGenerate={vi.fn()}
        onSwitch={onSwitch}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /switch to/i }));
    expect(onSwitch).toHaveBeenCalledWith("yoga", "/abs/yoga");
  });

  it("renders typed error panels", () => {
    render(
      <OnboardingWizard
        isPending={false}
        error={{ kind: "SidecarDown", detail: { message: "down" } }}
        result={null}
        onGenerate={vi.fn()}
        onSwitch={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i);
  });
});
