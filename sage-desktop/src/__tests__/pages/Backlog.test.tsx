import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import * as client from "@/api/client";
import { createTestQueryClient } from "../helpers/queryWrapper";
import Backlog from "@/pages/Backlog";

// CRITICAL: mock with a factory that preserves the real module — a bare
// vi.mock("@/api/client") auto-mocks every export including the pure
// toDesktopError() helper, silently turning it into a stub that returns
// undefined and breaking the error-banner assertions below.
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    listFeatureRequests: vi.fn(),
    submitFeatureRequest: vi.fn(),
    updateFeatureRequest: vi.fn(),
    planFeatureRequest: vi.fn(),
  };
});

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

  it("generates a plan and shows the GitHub issue link for a sage-scope request", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([{
      id: "1", title: "Add MCP tool", description: "",
      priority: "medium", status: "pending", scope: "sage",
      module_id: "general", module_name: "General", requested_by: "a",
      created_at: "", updated_at: "", reviewer_note: "", plan_trace_id: "",
    }] as any);
    vi.mocked(client.planFeatureRequest).mockResolvedValue({
      request_id: "1",
      status: "github_pr",
      github_issue_url: "https://github.com/Sumanharapanahalli/SAGE/issues/new?title=x",
      message: "SAGE framework improvements are contributed via GitHub.",
    } as any);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Backlog />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("Add MCP tool")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /generate plan/i }));
    await waitFor(() => expect(client.planFeatureRequest).toHaveBeenCalledWith("1"));
    const link = await screen.findByRole("link", { name: /github/i });
    expect(link).toHaveAttribute("href", expect.stringContaining("github.com"));
  });

  it("generates a plan and links to Approvals for a solution-scope request", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([{
      id: "2", title: "Dark mode", description: "",
      priority: "medium", status: "approved", scope: "solution",
      module_id: "general", module_name: "General", requested_by: "a",
      created_at: "", updated_at: "", reviewer_note: "", plan_trace_id: "",
    }] as any);
    vi.mocked(client.planFeatureRequest).mockResolvedValue({
      trace_id: "trace-1",
      action_type: "implementation_plan",
      risk_class: "STATEFUL",
      status: "pending",
      description: "Implementation plan: Dark mode",
    } as any);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Backlog />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("Dark mode")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /generate plan/i }));
    await waitFor(() => expect(client.planFeatureRequest).toHaveBeenCalledWith("2"));
    const link = await screen.findByRole("link", { name: /approvals/i });
    expect(link).toHaveAttribute("href", "/approvals");
  });

  it("does not show a Generate Plan button for a request already in planning", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([{
      id: "3", title: "Already planned", description: "",
      priority: "medium", status: "in_planning", scope: "solution",
      module_id: "general", module_name: "General", requested_by: "a",
      created_at: "", updated_at: "", reviewer_note: "", plan_trace_id: "trace-x",
    }] as any);
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Backlog />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("Already planned")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /generate plan/i })).not.toBeInTheDocument();
  });

  it("shows an error banner when the feature request list query fails", async () => {
    vi.mocked(client.listFeatureRequests).mockRejectedValue({
      kind: "SolutionUnavailable",
      detail: { message: "no solution loaded" },
    });
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Backlog />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const alert = await screen.findByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(/no solution loaded/i);
  });

  it("shows an error banner when submitting a feature request fails", async () => {
    vi.mocked(client.listFeatureRequests).mockResolvedValue([]);
    vi.mocked(client.submitFeatureRequest).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "title is required" },
    });
    render(
      <QueryClientProvider client={createTestQueryClient()}>
        <MemoryRouter>
          <Backlog />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await userEvent.type(screen.getByLabelText(/title/i), "new item");
    await userEvent.click(screen.getByRole("button", { name: /submit/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(screen.getByText(/InvalidParams/i)).toBeInTheDocument();
  });
});
