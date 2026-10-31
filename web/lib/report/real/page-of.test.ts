import { describe, expect, it } from "vitest";
import { pageOf } from "./codes";

describe("pageOf", () => {
  it("reads p3 and page 3", () => {
    for (const [text, page] of [["p3", 3], ["P3", 3], ["page 12", 12], ["Page 4", 4], ["p 7", 7]] as const) expect(pageOf(text)).toBe(page);
  });

  it("gives null for anything else", () => {
    for (const bad of ["page 0", "p0", "p", "page", "page 3x", "p3-4", "rows 1–4079", "", null, undefined, "p" + "9".repeat(40), "page -2"]) expect(pageOf(bad)).toBeNull();
  });
});
