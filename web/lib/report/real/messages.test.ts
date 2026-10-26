import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { CONFIDENCE_CODES, METHOD_CODES, REASON_CODES } from "./codes";

const sets = [["en", en.report], ["ko", ko.report]] as const;

function keys(value: unknown, prefix = ""): string[] {
  if (value && typeof value === "object") return Object.entries(value).flatMap(([k, v]) => keys(v, `${prefix}${k}.`));
  return [prefix];
}

describe("report messages", () => {
  it("en and ko have the same keys", () => {
    expect(keys(ko.report).sort()).toEqual(keys(en.report).sort());
  });

  it("workspace trace, ready and detail keys match too", () => {
    for (const part of ["trace", "real"] as const) expect(keys(ko.workspace[part]).sort(), part).toEqual(keys(en.workspace[part]).sort());
  });

  it.each(sets)("%s has a title and a text for every reason code and the neutral one", (_lang, report) => {
    const reasons = report.reason as Record<string, { title: string; body: string }>;
    for (const code of [...REASON_CODES, "unknown"]) {
      expect(reasons[code]?.title, code).toBeTruthy();
      expect(reasons[code]?.body, code).toBeTruthy();
    }
    expect(Object.keys(reasons).sort()).toEqual([...REASON_CODES, "unknown"].sort());
  });

  it.each(sets)("%s has a text for every method code and the neutral one", (_lang, report) => {
    const methods = report.method as Record<string, string>;
    for (const code of [...METHOD_CODES, "unknown"]) expect(methods[code], code).toBeTruthy();
    expect(Object.keys(methods).sort()).toEqual([...METHOD_CODES, "unknown"].sort());
  });

  it.each(sets)("%s has a confidence text for every level", (_lang, report) => {
    const levels = report.confidence as Record<string, string>;
    for (const code of CONFIDENCE_CODES) expect(levels[code], code).toBeTruthy();
  });

  it("the texts themselves never contain a raw code", () => {
    function values(value: unknown): string[] {
      if (value && typeof value === "object") return Object.values(value).flatMap(values);
      return [String(value)];
    }
    for (const [, report] of sets) {
      for (const text of values([report.reason, report.method])) {
        expect(text).not.toContain("_");
        expect([...REASON_CODES, ...METHOD_CODES] as string[]).not.toContain(text);
      }
    }
  });
});
