import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ErrorBanner } from "@/components/layout/ErrorBanner";

describe("ErrorBanner", () => {
  it("renders nothing when error is null", () => {
    const { container } = render(<ErrorBanner error={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows SidecarDown with a reconnect hint", () => {
    render(
      <ErrorBanner
        error={{ kind: "SidecarDown", detail: { message: "stream closed" } }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/sidecar/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/stream closed/i);
  });

  it("shows ProposalNotFound with the trace id", () => {
    render(
      <ErrorBanner
        error={{ kind: "ProposalNotFound", detail: { trace_id: "t-42" } }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/not found/i);
    expect(screen.getByRole("alert")).toHaveTextContent("t-42");
  });

  it("renders AlreadyDecided including status", () => {
    render(
      <ErrorBanner
        error={{
          kind: "AlreadyDecided",
          detail: { trace_id: "t-9", status: "approved" },
        }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/already/i);
    expect(screen.getByRole("alert")).toHaveTextContent("approved");
  });

  it("renders SolutionNotFound with the solution name", () => {
    render(
      <ErrorBanner
        error={{ kind: "SolutionNotFound", detail: { name: "yoga" } }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/solution not found/i);
    expect(screen.getByRole("alert")).toHaveTextContent("yoga");
  });

  it("falls back to Other with code + message", () => {
    render(
      <ErrorBanner
        error={{ kind: "Other", detail: { code: 42, message: "kaboom" } }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("kaboom");
  });
});
