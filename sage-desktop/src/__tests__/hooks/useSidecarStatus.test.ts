import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { sidecarStatusKey, useSidecarStatus } from "@/hooks/useSidecarStatus";
import { createTestQueryClient, wrapperWith } from "../helpers/queryWrapper";

describe("useSidecarStatus", () => {
  it("defaults to online when no sidecar-status event has fired yet", () => {
    const qc = createTestQueryClient();
    const { result } = renderHook(() => useSidecarStatus(), {
      wrapper: wrapperWith(qc),
    });
    expect(result.current.online).toBe(true);
  });

  it("reflects a cached offline status written by useAppEvents", () => {
    const qc = createTestQueryClient();
    qc.setQueryData(sidecarStatusKey, {
      online: false,
      reason: "sidecar exited unexpectedly",
    });
    const { result } = renderHook(() => useSidecarStatus(), {
      wrapper: wrapperWith(qc),
    });
    expect(result.current).toEqual({
      online: false,
      reason: "sidecar exited unexpectedly",
    });
  });
});
