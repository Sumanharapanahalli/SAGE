import { useQuery } from "@tanstack/react-query";

export interface SidecarStatus {
  online: boolean;
  reason?: string;
  exhausted?: boolean;
}

export const sidecarStatusKey = ["sidecarStatus"] as const;

const DEFAULT_STATUS: SidecarStatus = { online: true };

/** Current sidecar online/offline status, written to the query cache by
 * `useAppEvents` on every `sidecar-status` Tauri event. `useQuery` (not a
 * plain `getQueryData` read) so components subscribe and re-render when
 * `useAppEvents` calls `setQueryData` — there is no real queryFn/fetch here
 * (staleTime: Infinity means it never runs on its own); this is purely an
 * event-driven cache slot. Defaults to online until an event says
 * otherwise. */
export function useSidecarStatus(): SidecarStatus {
  const { data } = useQuery<SidecarStatus>({
    queryKey: sidecarStatusKey,
    queryFn: () => DEFAULT_STATUS,
    initialData: DEFAULT_STATUS,
    staleTime: Infinity,
    gcTime: Infinity,
  });
  return data;
}
