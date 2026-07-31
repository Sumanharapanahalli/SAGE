import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import * as client from "@/api/client";
import Organization from "@/pages/Organization";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

// CRITICAL: a factory-less vi.mock("@/api/client") auto-mocks every export,
// including the pure toDesktopError helper, into a stub returning undefined —
// which silently breaks ErrorBanner rendering. Spread `actual` and only
// override the org.* functions we drive in this test.
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    getOrg: vi.fn(),
    updateOrg: vi.fn(),
    reloadOrg: vi.fn(),
    addOrgRoute: vi.fn(),
    deleteOrgRoute: vi.fn(),
    createOrgChannel: vi.fn(),
    deleteOrgChannel: vi.fn(),
  };
});

const ORG_DATA = {
  org: {
    name: "Acme Corp",
    mission: "Only mission",
    vision: "A better world by 2040",
    core_values: ["Integrity", "Speed"],
  },
  routes: [{ source: "meditation_app", target: "billing" }],
};

function renderPage() {
  const Wrapper = wrapperWith(createTestQueryClient());
  return render(
    <Wrapper>
      <Organization />
    </Wrapper>,
  );
}

describe("Organization page", () => {
  beforeEach(() => vi.resetAllMocks());

  it("loads org identity fields and renders the read-only routes list", async () => {
    vi.mocked(client.getOrg).mockResolvedValue(ORG_DATA);
    renderPage();

    await waitFor(() =>
      expect(screen.getByDisplayValue("Acme Corp")).toBeInTheDocument(),
    );
    expect(screen.getByDisplayValue("Only mission")).toBeInTheDocument();
    expect(screen.getByDisplayValue("A better world by 2040")).toBeInTheDocument();
    expect(screen.getByDisplayValue(/Integrity/)).toBeInTheDocument();
    expect(screen.getByText(/meditation_app/)).toBeInTheDocument();
    expect(screen.getByText(/billing/)).toBeInTheDocument();
  });

  it("saves only the edited fields", async () => {
    vi.mocked(client.getOrg).mockResolvedValue(ORG_DATA);
    vi.mocked(client.updateOrg).mockResolvedValue({
      status: "saved",
      org: { ...ORG_DATA.org, name: "New Co" },
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByDisplayValue("Acme Corp")).toBeInTheDocument(),
    );
    const nameInput = screen.getByDisplayValue("Acme Corp");
    await user.clear(nameInput);
    await user.type(nameInput, "New Co");
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(client.updateOrg).toHaveBeenCalledWith({
        name: "New Co",
        mission: "Only mission",
        vision: "A better world by 2040",
        core_values: ["Integrity", "Speed"],
      }),
    );
  });

  it("renders an error banner when the save fails", async () => {
    vi.mocked(client.getOrg).mockResolvedValue(ORG_DATA);
    vi.mocked(client.updateOrg).mockRejectedValue({
      kind: "InvalidParams",
      detail: { message: "'name' must be a string" },
    });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByDisplayValue("Acme Corp")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() =>
      expect(screen.getByText(/must be a string/i)).toBeInTheDocument(),
    );
  });

  it("reloads org.yaml on demand", async () => {
    vi.mocked(client.getOrg).mockResolvedValue(ORG_DATA);
    vi.mocked(client.reloadOrg).mockResolvedValue({ status: "reloaded" });
    const user = userEvent.setup();
    renderPage();

    await waitFor(() =>
      expect(screen.getByDisplayValue("Acme Corp")).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /reload/i }));

    await waitFor(() => expect(client.reloadOrg).toHaveBeenCalled());
  });

  it("shows a message when there are no cross-team routes", async () => {
    vi.mocked(client.getOrg).mockResolvedValue({ org: {}, routes: [] });
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/no cross-team routes/i)).toBeInTheDocument(),
    );
  });
});

// ── Item 5: routes and channels are now writable ────────────────────────────

describe("Organization page — routes and channels", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(client.getOrg).mockResolvedValue({
      ...ORG_DATA,
      org: {
        ...ORG_DATA.org,
        knowledge_channels: { alerts: { producers: [], consumers: [] } },
      },
    } as never);
  });

  it("adds a route naming the SOURCE solution, since routes live in its project.yaml", async () => {
    vi.mocked(client.addOrgRoute).mockResolvedValue({
      status: "added",
      solution: "meditation_app",
      target: "payments",
    });
    const user = userEvent.setup();
    render(<Organization />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/cross-team routes/i)).toBeInTheDocument(),
    );

    await user.type(screen.getByLabelText(/from solution/i), "meditation_app");
    await user.type(screen.getByLabelText(/to solution/i), "payments");
    await user.click(screen.getByRole("button", { name: /add route/i }));

    await waitFor(() =>
      expect(client.addOrgRoute).toHaveBeenCalledWith(
        "meditation_app",
        "payments",
      ),
    );
  });

  it("removes a route using its source solution", async () => {
    vi.mocked(client.deleteOrgRoute).mockResolvedValue({
      status: "removed",
      solution: "meditation_app",
      target: "billing",
    });
    const user = userEvent.setup();
    render(<Organization />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/meditation_app/)).toBeInTheDocument(),
    );

    await user.click(screen.getAllByRole("button", { name: /remove/i })[0]);

    await waitFor(() =>
      expect(client.deleteOrgRoute).toHaveBeenCalledWith(
        "meditation_app",
        "billing",
      ),
    );
  });

  it("lists existing knowledge channels", async () => {
    render(<Organization />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() => expect(screen.getByText("alerts")).toBeInTheDocument());
  });

  it("creates a knowledge channel", async () => {
    vi.mocked(client.createOrgChannel).mockResolvedValue({
      status: "created",
      channel: "incidents",
    });
    const user = userEvent.setup();
    render(<Organization />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/knowledge channels/i)).toBeInTheDocument(),
    );

    await user.type(screen.getByLabelText(/channel name/i), "incidents");
    await user.click(screen.getByRole("button", { name: /add channel/i }));

    await waitFor(() =>
      expect(client.createOrgChannel).toHaveBeenCalledWith("incidents", [], []),
    );
  });

  it("does not add a route until both solutions are named", async () => {
    render(<Organization />, { wrapper: wrapperWith(createTestQueryClient()) });
    await waitFor(() =>
      expect(screen.getByText(/cross-team routes/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: /add route/i })).toBeDisabled();
  });
});
