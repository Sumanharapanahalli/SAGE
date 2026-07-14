import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as client from "@/api/client";
import { useLogTail } from "@/hooks/useLogs";

// Keep the real module and stub only `tailLogs` — a bare vi.mock() would also
// auto-mock the pure `toDesktopError` helper the hook uses to normalize errors.
vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return { ...actual, tailLogs: vi.fn() };
});

const entry = (seq: number, message: string, level = "INFO") => ({
  seq,
  ts: "2026-07-13T10:00:00+00:00",
  level,
  name: "src.test",
  message,
});

describe("useLogTail", () => {
  beforeEach(() => vi.resetAllMocks());

  it("appends entries from the first poll and reports connected", async () => {
    vi.mocked(client.tailLogs).mockResolvedValue({
      entries: [entry(1, "hello console")],
      last_seq: 1,
      buffered: 1,
      capacity: 500,
      installed: true,
    });

    const { result } = renderHook(() => useLogTail(false));

    await waitFor(() => expect(result.current.entries).toHaveLength(1));
    expect(result.current.entries[0].message).toBe("hello console");
    expect(result.current.connected).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("advances the cursor so the next poll only asks for newer records", async () => {
    vi.mocked(client.tailLogs).mockResolvedValue({
      entries: [entry(1, "one"), entry(2, "two")],
      last_seq: 2,
      buffered: 2,
      capacity: 500,
      installed: true,
    });

    const { result } = renderHook(() => useLogTail(false));
    await waitFor(() => expect(result.current.entries).toHaveLength(2));

    // First poll starts at the zero cursor…
    expect(vi.mocked(client.tailLogs).mock.calls[0][0]).toBe(0);
    // …and the next one (POLL_MS = 2000) resumes from last_seq, so records
    // are never re-fetched and never duplicated in the display buffer.
    await waitFor(
      () =>
        expect(vi.mocked(client.tailLogs).mock.calls.length).toBeGreaterThan(1),
      { timeout: 4000 },
    );
    const calls = vi.mocked(client.tailLogs).mock.calls;
    expect(calls[calls.length - 1][0]).toBe(2);
  });

  it("does not poll while paused", async () => {
    vi.mocked(client.tailLogs).mockResolvedValue({
      entries: [],
      last_seq: 0,
      buffered: 0,
      capacity: 500,
      installed: true,
    });

    renderHook(() => useLogTail(true));
    // Give the effect's first tick a chance to run.
    await new Promise((r) => setTimeout(r, 20));
    expect(client.tailLogs).not.toHaveBeenCalled();
  });

  it("surfaces a transport failure and marks itself disconnected", async () => {
    vi.mocked(client.tailLogs).mockRejectedValue({
      kind: "SidecarDown",
      detail: { message: "stream closed" },
    });

    const { result } = renderHook(() => useLogTail(false));

    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.connected).toBe(false);
    expect(result.current.error?.kind).toBe("SidecarDown");
  });

  it("clear() empties the display buffer", async () => {
    vi.mocked(client.tailLogs).mockResolvedValue({
      entries: [entry(1, "noise")],
      last_seq: 1,
      buffered: 1,
      capacity: 500,
      installed: true,
    });

    const { result } = renderHook(() => useLogTail(false));
    await waitFor(() => expect(result.current.entries).toHaveLength(1));

    act(() => result.current.clear());
    expect(result.current.entries).toHaveLength(0);
  });
});
