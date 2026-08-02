import { describe, expect, it } from "vitest";

import { normalizeTaskTypes } from "@/lib/taskTypes";

describe("normalizeTaskTypes", () => {
  it("maps the {name, description} objects agent_factory asks the LLM for", () => {
    expect(
      normalizeTaskTypes([
        { name: "LOG_REVIEW", description: "review a log" },
        { name: "DIFF_REVIEW", description: "review a diff" },
      ]),
    ).toEqual(["LOG_REVIEW", "DIFF_REVIEW"]);
  });

  it("passes plain strings through", () => {
    // The prompt asks for objects, but this is unvalidated LLM output and
    // nothing enforces the shape. web/src/pages/Agents.tsx:262 does a bare
    // `t.name`, which silently yields [undefined] for this input — and
    // agentrun.hire then rejects the whole payload.
    expect(normalizeTaskTypes(["LOG_REVIEW"])).toEqual(["LOG_REVIEW"]);
  });

  it("handles a mixed array", () => {
    expect(normalizeTaskTypes([{ name: "A" }, "B"])).toEqual(["A", "B"]);
  });

  it("drops entries with no usable name instead of emitting undefined", () => {
    // agentrun.hire rejects the ENTIRE payload if any element is not a
    // string, so one malformed entry must not poison the hire.
    expect(
      normalizeTaskTypes([{ name: "A" }, {} as never, "", "  ", "B"]),
    ).toEqual(["A", "B"]);
  });

  it("returns [] for a non-array (task_types is optional on hire)", () => {
    expect(normalizeTaskTypes(undefined)).toEqual([]);
    expect(normalizeTaskTypes(null as never)).toEqual([]);
  });

  it("trims surrounding whitespace", () => {
    expect(normalizeTaskTypes([{ name: "  A  " }, " B "])).toEqual(["A", "B"]);
  });
});
