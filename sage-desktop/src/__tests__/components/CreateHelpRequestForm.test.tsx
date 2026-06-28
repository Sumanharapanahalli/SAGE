import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CreateHelpRequestForm } from "@/components/domain/CreateHelpRequestForm";

describe("CreateHelpRequestForm", () => {
  it("submits the full payload with parsed expertise list", () => {
    const spy = vi.fn();
    render(<CreateHelpRequestForm onSubmit={spy} />);
    fireEvent.change(screen.getByLabelText(/^title$/i), {
      target: { value: "I2C help" },
    });
    fireEvent.change(screen.getByLabelText(/requester_agent/i), {
      target: { value: "developer" },
    });
    fireEvent.change(screen.getByLabelText(/requester_solution/i), {
      target: { value: "automotive" },
    });
    fireEvent.change(screen.getByLabelText(/urgency/i), {
      target: { value: "critical" },
    });
    fireEvent.change(screen.getByLabelText(/required_expertise/i), {
      target: { value: " i2c , stm32 " },
    });
    fireEvent.change(screen.getByLabelText(/context/i), {
      target: { value: "Stuck." },
    });
    fireEvent.click(screen.getByRole("button", { name: /create/i }));
    expect(spy).toHaveBeenCalledWith({
      title: "I2C help",
      requester_agent: "developer",
      requester_solution: "automotive",
      urgency: "critical",
      required_expertise: ["i2c", "stm32"],
      context: "Stuck.",
    });
  });

  it("defaults urgency to medium and disables create when incomplete", () => {
    const spy = vi.fn();
    render(<CreateHelpRequestForm onSubmit={spy} />);
    const btn = screen.getByRole("button", { name: /create/i });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/^title$/i), {
      target: { value: "x" },
    });
    fireEvent.change(screen.getByLabelText(/requester_agent/i), {
      target: { value: "a" },
    });
    fireEvent.change(screen.getByLabelText(/requester_solution/i), {
      target: { value: "s" },
    });
    expect(btn).not.toBeDisabled();
    fireEvent.click(btn);
    expect(spy).toHaveBeenCalledWith({
      title: "x",
      requester_agent: "a",
      requester_solution: "s",
      urgency: "medium",
      required_expertise: [],
      context: "",
    });
  });

  it("offers the four urgency options", () => {
    render(<CreateHelpRequestForm onSubmit={() => {}} />);
    const select = screen.getByLabelText(/urgency/i) as HTMLSelectElement;
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toEqual(["low", "medium", "high", "critical"]);
  });
});
