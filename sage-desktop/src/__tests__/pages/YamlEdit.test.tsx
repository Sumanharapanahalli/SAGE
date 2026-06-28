import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/client", () => ({
  readYaml: vi.fn().mockResolvedValue({
    file: "project",
    solution: "demo",
    content: "name: demo\nversion: 1\n",
    path: "/abs/project.yaml",
  }),
  writeYaml: vi.fn().mockResolvedValue({
    file: "project",
    solution: "demo",
    path: "/abs/project.yaml",
    bytes: 30,
  }),
}));

import * as client from "@/api/client";
import YamlEdit from "@/pages/YamlEdit";

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={qc}>
        <YamlEdit />
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("YamlEdit page", () => {
  beforeEach(() => vi.clearAllMocks());

  it("loads project.yaml by default and shows its content", async () => {
    renderPage();
    await waitFor(() =>
      expect(client.readYaml).toHaveBeenCalledWith("project"),
    );
    expect(
      await screen.findByDisplayValue(/name: demo/),
    ).toBeInTheDocument();
  });

  it("saves the edited YAML through writeYaml", async () => {
    renderPage();
    const editor = (await screen.findByDisplayValue(
      /name: demo/,
    )) as HTMLTextAreaElement;
    fireEvent.change(editor, {
      target: { value: "name: demo\nversion: 2\n" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() =>
      expect(client.writeYaml).toHaveBeenCalledWith(
        "project",
        "name: demo\nversion: 2\n",
      ),
    );
  });

  it("disables Save when there are no pending edits", async () => {
    renderPage();
    await screen.findByDisplayValue(/name: demo/);
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });
});
