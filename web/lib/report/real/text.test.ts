import { describe, expect, it } from "vitest";
import { plainText } from "./text";

describe("plainText", () => {
  it("keeps markup and links as the text they are (React escapes them; nothing is parsed)", () => {
    expect(plainText("<script>alert(1)</script>")).toBe("<script>alert(1)</script>");
    expect(plainText("[x](https://evil.example)")).toBe("[x](https://evil.example)");
  });

  it("drops control and direction-override characters", () => {
    const bidi = String.fromCharCode(0x202e);
    const zero = String.fromCharCode(0x200b);
    const bell = String.fromCharCode(7);
    expect(plainText(`a${bidi}b${zero}c${bell}d`)).toBe("abcd");
  });

  it("turns line breaks and tabs into spaces", () => {
    expect(plainText("a\r\nb\tc")).toBe("a b c");
  });

  it("cuts a very long string and ends it with an ellipsis", () => {
    const out = plainText("x".repeat(1000), 50);
    expect(out).toHaveLength(50);
    expect(out.endsWith("…")).toBe(true);
  });

  it("returns an empty string for anything that is not a string", () => {
    for (const value of [null, undefined, 3, {}, []]) expect(plainText(value)).toBe("");
  });

  it("keeps Korean names with parentheses", () => {
    expect(plainText("잠실(송파구청)")).toBe("잠실(송파구청)");
  });
});
