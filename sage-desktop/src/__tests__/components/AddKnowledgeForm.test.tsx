import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AddKnowledgeForm } from "@/components/domain/AddKnowledgeForm";

describe("AddKnowledgeForm", () => {
  it("submits text with metadata pairs collapsed into an object", () => {
    const spy = vi.fn();
    render(<AddKnowledgeForm onSubmit={spy} />);

    fireEvent.change(screen.getByLabelText("entry text"), {
      target: { value: "Remember this." },
    });
    fireEvent.click(screen.getByRole("button", { name: /add metadata pair/i }));
    fireEvent.change(screen.getByLabelText("metadata key 1"), {
      target: { value: "source" },
    });
    fireEvent.change(screen.getByLabelText("metadata value 1"), {
      target: { value: "manual" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));

    expect(spy).toHaveBeenCalledWith("Remember this.", { source: "manual" });
  });

  it("disables submit when text is empty or whitespace", () => {
    render(<AddKnowledgeForm onSubmit={() => {}} />);
    const btn = screen.getByRole("button", { name: /^add$/i });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByLabelText("entry text"), {
      target: { value: "   " },
    });
    expect(btn).toBeDisabled();
  });
});
