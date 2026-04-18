import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PublishLearningForm } from "@/components/domain/PublishLearningForm";

function fill() {
  fireEvent.change(screen.getByLabelText(/author_agent/i), {
    target: { value: "analyst" },
  });
  fireEvent.change(screen.getByLabelText(/author_solution/i), {
    target: { value: "medtech" },
  });
  fireEvent.change(screen.getByLabelText(/topic/i), {
    target: { value: "uart" },
  });
  fireEvent.change(screen.getByLabelText(/title/i), {
    target: { value: "UART recovery" },
  });
  fireEvent.change(screen.getByLabelText(/content/i), {
    target: { value: "Flush and retry." },
  });
}

describe("PublishLearningForm", () => {
  it("submits the full payload including parsed tags", () => {
    const spy = vi.fn();
    render(<PublishLearningForm onSubmit={spy} />);
    fill();
    fireEvent.change(screen.getByLabelText(/tags/i), {
      target: { value: " uart , embedded,,recovery " },
    });
    fireEvent.change(screen.getByLabelText(/confidence/i), {
      target: { value: "0.8" },
    });
    fireEvent.click(screen.getByRole("button", { name: /publish/i }));
    expect(spy).toHaveBeenCalledWith({
      author_agent: "analyst",
      author_solution: "medtech",
      topic: "uart",
      title: "UART recovery",
      content: "Flush and retry.",
      tags: ["uart", "embedded", "recovery"],
      confidence: 0.8,
    });
  });

  it("disables publish until all required fields are filled", () => {
    render(<PublishLearningForm onSubmit={() => {}} />);
    const btn = screen.getByRole("button", { name: /publish/i });
    expect(btn).toBeDisabled();
    fill();
    expect(btn).not.toBeDisabled();
  });

  it("omits empty optional fields from the payload", () => {
    const spy = vi.fn();
    render(<PublishLearningForm onSubmit={spy} />);
    fill();
    fireEvent.click(screen.getByRole("button", { name: /publish/i }));
    expect(spy).toHaveBeenCalledWith({
      author_agent: "analyst",
      author_solution: "medtech",
      topic: "uart",
      title: "UART recovery",
      content: "Flush and retry.",
      tags: [],
      confidence: 0.5,
    });
  });
});
