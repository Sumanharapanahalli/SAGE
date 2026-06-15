// Shared date/time formatting — single source of truth for relative timestamps.
// Consolidates copies previously duplicated in Activity, Issues, Approvals, and
// ProposalCard (Gemini web-reuse finding #3: "extract shared logic").

/**
 * Human-friendly relative time, e.g. "just now", "5m ago", "3h ago", "2d ago".
 * Falls back to a locale date string for anything older than ~30 days.
 *
 * Accepts an ISO string, a Date, or epoch milliseconds.
 */
export function formatRelativeTime(input: string | number | Date): string {
  const then = input instanceof Date ? input.getTime() : new Date(input).getTime();
  if (Number.isNaN(then)) return '';

  const diff = Date.now() - then;
  const mins = Math.floor(diff / 60_000);
  const hours = Math.floor(diff / 3_600_000);
  const days = Math.floor(diff / 86_400_000);

  if (mins < 2) return 'just now';
  if (hours < 1) return `${mins}m ago`;
  if (days < 1) return `${hours}h ago`;
  if (days < 30) return `${days}d ago`;
  return new Date(then).toLocaleDateString();
}
