import { beforeEach, describe, expect, it } from "vitest";

import { getLastSolution, setLastSolution } from "@/lib/lastSolution";

describe("lastSolution", () => {
  beforeEach(() => localStorage.clear());

  it("returns null when nothing is stored", () => {
    expect(getLastSolution()).toBeNull();
  });

  it("round-trips a stored solution", () => {
    setLastSolution({ name: "poseengine", path: "/sol/poseengine" });
    expect(getLastSolution()).toEqual({
      name: "poseengine",
      path: "/sol/poseengine",
    });
  });

  it("returns null for malformed JSON", () => {
    localStorage.setItem("sage-desktop:last-solution", "{not json");
    expect(getLastSolution()).toBeNull();
  });

  it("returns null for a JSON value missing required fields", () => {
    localStorage.setItem(
      "sage-desktop:last-solution",
      JSON.stringify({ name: "x" }),
    );
    expect(getLastSolution()).toBeNull();
  });
});
