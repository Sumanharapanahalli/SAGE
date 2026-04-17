import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FeatureRequestRow } from "@/components/domain/FeatureRequestRow";
import type { FeatureRequest } from "@/api/types";

const fr: FeatureRequest = {
  id: "abc",
  module_id: "general",
  module_name: "General",
  title: "Add dark mode",
  description: "Users want it",
  priority: "high",
  status: "pending",
  requested_by: "alice",
  scope: "solution",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  reviewer_note: "",
  plan_trace_id: "",
};

describe("FeatureRequestRow", () => {
  it("renders title, priority and status", () => {
    render(<FeatureRequestRow item={fr} onAction={() => {}} isPending={false} />);
    expect(screen.getByText("Add dark mode")).toBeInTheDocument();
    expect(screen.getByText(/high/i)).toBeInTheDocument();
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
  });

  it("emits approve action with id", async () => {
    const onAction = vi.fn();
    render(<FeatureRequestRow item={fr} onAction={onAction} isPending={false} />);
    await userEvent.click(screen.getByRole("button", { name: /approve/i }));
    expect(onAction).toHaveBeenCalledWith("abc", "approve");
  });

  it("hides action buttons when not pending", () => {
    const approved: FeatureRequest = { ...fr, status: "approved" };
    render(<FeatureRequestRow item={approved} onAction={() => {}} isPending={false} />);
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });
});
