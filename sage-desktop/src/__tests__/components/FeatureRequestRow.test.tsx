import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { FeatureRequestRow } from "@/components/domain/FeatureRequestRow";
import type { FeatureRequest } from "@/api/types";
import { createTestQueryClient } from "../helpers/queryWrapper";

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

// FeatureRequestRow now owns a usePlanFeatureRequest() mutation (react-query)
// and renders a <Link> on success, so it needs both providers even for tests
// that never touch the "Generate Plan" button.
function renderRow(item: FeatureRequest, onAction: (id: string, action: string) => void, isPending: boolean) {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>
        <FeatureRequestRow item={item} onAction={onAction} isPending={isPending} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("FeatureRequestRow", () => {
  it("renders title, priority and status", () => {
    renderRow(fr, () => {}, false);
    expect(screen.getByText("Add dark mode")).toBeInTheDocument();
    expect(screen.getByText(/high/i)).toBeInTheDocument();
    expect(screen.getByText(/pending/i)).toBeInTheDocument();
  });

  it("emits approve action with id", async () => {
    const onAction = vi.fn();
    renderRow(fr, onAction, false);
    await userEvent.click(screen.getByRole("button", { name: /approve/i }));
    expect(onAction).toHaveBeenCalledWith("abc", "approve");
  });

  it("hides action buttons when not pending", () => {
    const approved: FeatureRequest = { ...fr, status: "approved" };
    renderRow(approved, () => {}, false);
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });
});
