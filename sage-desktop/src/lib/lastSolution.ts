const KEY = "sage-desktop:last-solution";

export interface LastSolution {
  name: string;
  path: string;
}

/** Read the last-used solution from localStorage. Returns null if unset or malformed. */
export function getLastSolution(): LastSolution | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed.name === "string" &&
      typeof parsed.path === "string"
    ) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/** Remember a solution as the one to auto-reopen on next launch. */
export function setLastSolution(solution: LastSolution): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(solution));
  } catch {
    // localStorage can throw (quota, disabled) — auto-reopen is a nicety, not critical.
  }
}
