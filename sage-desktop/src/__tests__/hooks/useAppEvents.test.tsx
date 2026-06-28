import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Handler = (event: { payload: unknown }) => void;

const listeners = new Map<string, Set<Handler>>();
const unlisten = vi.fn();

vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn((name: string, cb: Handler) => {
    let set = listeners.get(name);
    if (!set) {
      set = new Set();
      listeners.set(name, set);
    }
    set.add(cb);
    return Promise.resolve(() => {
      set?.delete(cb);
      unlisten();
    });
  }),
}));

import { useAppEvents } from "@/hooks/useAppEvents";

function Probe() {
  useAppEvents();
  return null;
}

function wrap(qc: QueryClient) {
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("useAppEvents", () => {
  beforeEach(() => {
    listeners.clear();
    unlisten.mockClear();
  });

  afterEach(() => {
    listeners.clear();
  });

  it("invalidates all queries when solution-switched fires", async () => {
    const qc = new QueryClient();
    const spy = vi.spyOn(qc, "invalidateQueries");

    const Wrapper = wrap(qc);
    render(
      <Wrapper>
        <Probe />
      </Wrapper>,
    );

    // Wait for the async listen subscription to resolve.
    await waitFor(() =>
      expect(listeners.get("solution-switched")?.size).toBeGreaterThan(0),
    );

    const handlers = listeners.get("solution-switched")!;
    for (const h of handlers) {
      h({ payload: { name: "yoga", path: "/abs/yoga" } });
    }

    expect(spy).toHaveBeenCalled();
  });

  it("unsubscribes on unmount", async () => {
    const qc = new QueryClient();
    const Wrapper = wrap(qc);
    const { unmount } = render(
      <Wrapper>
        <Probe />
      </Wrapper>,
    );

    await waitFor(() =>
      expect(listeners.get("solution-switched")?.size).toBeGreaterThan(0),
    );

    unmount();
    await waitFor(() => expect(unlisten).toHaveBeenCalled());
  });
});
