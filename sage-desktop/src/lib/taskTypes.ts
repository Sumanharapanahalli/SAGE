import type { AgentTaskTypeDraft } from "@/api/types";

/**
 * Flatten an LLM-drafted `task_types` list into the plain strings
 * `agentrun.hire` accepts.
 *
 * `agent_factory` prompts the LLM for objects (`{name, description}`) while
 * the hire payload validates `all(isinstance(t, str))` — so a draft can never
 * be handed to hire unmapped. Nothing enforces the LLM's output shape, so
 * strings are accepted too, and unusable entries are dropped rather than
 * passed through as `undefined`: hire rejects the ENTIRE payload if a single
 * element is not a string, so one malformed entry would otherwise poison the
 * whole request.
 */
export function normalizeTaskTypes(
  raw: Array<AgentTaskTypeDraft | string> | undefined | null,
): string[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((t) => (typeof t === "string" ? t : (t?.name ?? "")))
    .map((s) => (typeof s === "string" ? s.trim() : ""))
    .filter((s) => s.length > 0);
}
