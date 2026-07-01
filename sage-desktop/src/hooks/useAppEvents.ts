import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

import { sidecarStatusKey } from "@/hooks/useSidecarStatus";

/**
 * Subscribe to cross-app Tauri events and invalidate React Query caches.
 *
 * Currently wired:
 * - `solution-switched` — emitted by the Rust `switch_solution` command
 *   after a successful sidecar respawn. We invalidate every query because
 *   the new sidecar has fresh `.sage/` state (different proposals, audit,
 *   queue, etc.).
 * - `sidecar-status` — emitted by the Rust crash-recovery hook
 *   (`{online, reason?, exhausted?}`) whenever the sidecar exits
 *   unexpectedly and again when it recovers. Cached under `sidecarStatus`
 *   (see `useSidecarStatus`) rather than triggering an effect directly, so
 *   any number of components can read the current status.
 */
export function useAppEvents(): void {
  const qc = useQueryClient();
  useEffect(() => {
    const unlistenFns: UnlistenFn[] = [];
    let cancelled = false;
    (async () => {
      const solutionFn = await listen("solution-switched", () => {
        qc.invalidateQueries();
      });
      const statusFn = await listen<{
        online: boolean;
        reason?: string;
        exhausted?: boolean;
      }>("sidecar-status", (event) => {
        qc.setQueryData(sidecarStatusKey, event.payload);
      });
      if (cancelled) {
        solutionFn();
        statusFn();
      } else {
        unlistenFns.push(solutionFn, statusFn);
      }
    })().catch(() => {
      // In vitest/non-Tauri contexts `listen` may throw — harmless.
    });
    return () => {
      cancelled = true;
      unlistenFns.forEach((fn) => fn());
    };
  }, [qc]);
}
