import { describe, expect, it } from "vitest";
import { displayInitial } from "./display";

describe("displayInitial", () => {
  it("takes the first letter of a Latin name, upper-cased", () => {
    expect(displayInitial("  ada", "x@example.com")).toBe("A");
  });

  it("takes the first Hangul syllable, composed even when typed as jamo", () => {
    expect(displayInitial("김민수", "x@example.com")).toBe("김");
    expect(displayInitial("김민수".normalize("NFD"), "")).toBe("김");
  });

  it("falls back to the first letter of the email when the name is empty", () => {
    expect(displayInitial("", "kim@example.com")).toBe("K");
    expect(displayInitial("   ", "  zoe@example.com")).toBe("Z");
  });

  it("falls back to a question mark when both are empty", () => {
    expect(displayInitial("", "")).toBe("?");
    expect(displayInitial("  ", "  ")).toBe("?");
    expect(displayInitial("")).toBe("?");
  });
});
