import { useSidecarStatus } from "@/hooks/useSidecarStatus";

/** Global banner for the sidecar crash-recovery lifecycle (Rust
 * `on_crash` hook -> `sidecar-status` event -> useAppEvents cache write).
 * Renders nothing while online; while a recovery attempt is in flight
 * (1s/3s/9s backoff) it says so, and if that backoff is exhausted it tells
 * the operator how to actually recover (a manual solution switch respawns
 * the sidecar; restarting the app also works). */
export function SidecarStatusBanner() {
  const status = useSidecarStatus();
  if (status.online) return null;

  const exhausted = status.exhausted === true;
  return (
    <div
      role="alert"
      className={
        "px-4 py-2 text-sm font-medium text-center " +
        (exhausted
          ? "bg-red-100 text-red-900 border-b border-red-200"
          : "bg-amber-100 text-amber-900 border-b border-amber-200")
      }
    >
      {exhausted
        ? "Sidecar could not be recovered — restart the app or switch solutions to reconnect."
        : "Sidecar disconnected — attempting to reconnect…"}
    </div>
  );
}
