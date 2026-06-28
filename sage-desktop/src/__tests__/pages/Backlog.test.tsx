import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Backlog from "@/pages/Backlog";

vi.mock("@/api/client");

describe("Backlog page", () => {
  it("renders feature request list", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([{
      id: "1", title: "Dark mode", description: "",
      priority: "medium", status: "pending", scope: "solution",
      module_id: "general", module_name: "General", requested_by: "a",
      created_at: "", updated_at: "", reviewer_note: "", plan_trace_id: "",
    }] as any);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Backlog />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("Dark mode")).toBeInTheDocument());
  });

  it("submits a new feature request", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([]);
    vi.mocked(client.submitFeatureRequest).mockResolvedValue({
      id: "new", title: "new item", description: "body",
      priority: "medium", status: "pending", scope: "solution",
      module_id: "general", module_name: "General", requested_by: "anonymous",
      created_at: "", updated_at: "", reviewer_note: "", plan_trace_id: "",
    } as any);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Backlog />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.type(screen.getByLabelText(/title/i), "new item");
    await userEvent.type(screen.getByLabelText(/description/i), "body");
    await userEvent.click(screen.getByRole("button", { name: /submit/i }));
    await waitFor(() =>
      expect(client.submitFeatureRequest).toHaveBeenCalledWith(
        expect.objectContaining({ title: "new item", description: "body" }),
      ),
    );
  });
});
