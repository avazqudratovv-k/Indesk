import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { formatPageList } from "./format-page-list";

describe("formatPageList", () => {
  it("English: one, two, three and none", () => {
    expect(formatPageList([1], "en")).toBe("1");
    expect(formatPageList([1, 2], "en")).toBe("1 and 2");
    expect(formatPageList([1, 2, 3], "en")).toBe("1, 2 and 3");
    expect(formatPageList([], "en")).toBe("");
  });

  it("Korean: one, two, three and none", () => {
    expect(formatPageList([1], "ko")).toBe("1");
    expect(formatPageList([1, 2], "ko")).toBe("1 및 2");
    expect(formatPageList([1, 2, 3], "ko")).toBe("1, 2 및 3");
    expect(formatPageList([], "ko")).toBe("");
  });
});

describe("copy parity and register", () => {
  const flat = (o: unknown): string[] => (typeof o === "string" ? [o] : o && typeof o === "object" ? Object.values(o).flatMap(flat) : []);
  const keys = (o: unknown, p = ""): string[] => (o && typeof o === "object" ? Object.entries(o).flatMap(([k, v]) => keys(v, `${p}${k}.`)) : [p]);

  it("en and ko have the same keys", () => {
    expect(keys(ko).sort()).toEqual(keys(en).sort());
  });

  it("Korean has no particle markers in the changed groups", () => {
    const text = flat([ko.workspace.real.na, ko.workspace.trace, ko.plans.checkout]).join(" ");
    expect(text).not.toMatch(/\([은는이가을를]\)/);
  });

  it("the Free-plan sentence is its own key, so a signed-out visitor never gets it", () => {
    expect(en.plans.checkout.successLine).not.toContain("Free plan");
    expect(ko.plans.checkout.successLine).not.toContain("무료 플랜");
    expect(en.plans.checkout.successAccountFree).toContain("Free plan");
    expect(ko.plans.checkout.successAccountFree).toContain("무료 플랜");
  });
});
