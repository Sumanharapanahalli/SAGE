import { useCallback, useEffect, useRef, useState } from "react";

import { tailLogs, toDesktopError } from "@/api/client";
import type { DesktopError, LogEntry } from "@/api/types";

/** Client-side ring buffer size — mirrors the sidecar's deque capacity so the
 * page can show the full server-side backlog after a late open. */
export const MAX_LINES = 500;
const POLL_MS = 2000;

interface UseLogTailResult {
  entries: LogEntry[];
  connected: boolean;
  error: DesktopError | null;
  clear: () => void;
}

/**
 * Polls `logs.tail` on a cursor. The sidecar cannot stream (one-shot NDJSON),
 * so this replaces the web page's EventSource — the observable behaviour is the
 * same: an append-only, bounded, live-updating buffer.
 *
 * While `paused`, polling stops but the cursor is NOT advanced — records keep
 * accumulating in the sidecar's deque, and resuming replays everything since
 * the pause (up to the 500-record capacity). Web's SSE version silently
 * *dropped* records while paused; not advancing the cursor is strictly better
 * and costs nothing.
 *
 * `clear()` empties the display buffer only — the cursor stays put, so cleared
 * lines never reappear on the next poll.
 */
export function useLogTail(paused: boolean): UseLogTailResult {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<DesktopError | null>(null);

  const cursor = useRef(0);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      if (!pausedRef.current) {
        try {
          const res = await tailLogs(cursor.current, MAX_LINES);
          if (cancelled) return;
          setConnected(true);
          setError(null);
          if (res.entries.length > 0) {
            cursor.current = res.last_seq;
            setEntries((prev) => {
              const next = [...prev, ...res.entries];
              return next.length > MAX_LINES
                ? next.slice(next.length - MAX_LINES)
                : next;
            });
          }
        } catch (e) {
          if (cancelled) return;
          setConnected(false);
          setError(toDesktopError(e));
        }
      }
      if (!cancelled) timer = setTimeout(poll, POLL_MS);
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, []);

  const clear = useCallback(() => setEntries([]), []);

  return { entries, connected, error, clear };
}
