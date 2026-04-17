import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

/**
 * Subscribe to cross-app Tauri events and invalidate React Query caches.
 *
 * Currently wired:
 * - `solution-switched` — emitted by the Rust `switch_solution` command
 *   after a successful sidecar respawn. We invalidate every query because
 *   the new sidecar has fresh `.sage/` state (different proposals, audit,
 *   queue, etc.).
 */
export function useAppEvents(): void {
  const qc = useQueryClient();
  useEffect(() => {
    let unlisten: UnlistenFn | undefined;
    let cancelled = false;
    (async () => {
      const fn = await listen("solution-switched", () => {
        qc.invalidateQueries();
      });
      if (cancelled) {
        fn();
      } else {
        unlisten = fn;
      }
    })().catch(() => {
      // In vitest/non-Tauri contexts `listen` may throw — harmless.
    });
    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [qc]);
}
