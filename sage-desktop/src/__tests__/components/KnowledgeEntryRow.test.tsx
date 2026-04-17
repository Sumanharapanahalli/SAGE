import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { KnowledgeEntry } from "@/api/types";
import { KnowledgeEntryRow } from "@/components/domain/KnowledgeEntryRow";

const SHORT: KnowledgeEntry = {
  id: "uuid-1",
  text: "short entry",
  metadata: { source: "manual", tag: "demo" },
};

const LONG: KnowledgeEntry = {
  id: "uuid-2",
  text: "x".repeat(500),
  metadata: {},
};

describe("KnowledgeEntryRow", () => {
  it("renders id, metadata tags, and text preview", () => {
    render(<KnowledgeEntryRow entry={SHORT} onDelete={() => {}} />);
    expect(screen.getByText("uuid-1")).toBeInTheDocument();
    expect(screen.getByText("source=manual")).toBeInTheDocument();
    expect(screen.getByText("tag=demo")).toBeInTheDocument();
    expect(screen.getByText("short entry")).toBeInTheDocument();
  });

  it("requires a second click to confirm deletion and then calls onDelete", () => {
    const spy = vi.fn();
    render(<KnowledgeEntryRow entry={SHORT} onDelete={spy} />);
    fireEvent.click(screen.getByLabelText("delete entry uuid-1"));
    expect(spy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /confirm/i }));
    expect(spy).toHaveBeenCalledWith("uuid-1");
  });

  it("shows expand/collapse for long text", () => {
    render(<KnowledgeEntryRow entry={LONG} onDelete={() => {}} />);
    const expandBtn = screen.getByRole("button", { name: /expand/i });
    expect(expandBtn).toBeInTheDocument();
    fireEvent.click(expandBtn);
    expect(
      screen.getByRole("button", { name: /collapse/i }),
    ).toBeInTheDocument();
  });
});
