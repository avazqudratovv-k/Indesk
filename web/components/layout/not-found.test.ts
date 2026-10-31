import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";

describe("root not-found page", () => {
  it("has en and ko copy for title, body and home", () => {
    for (const m of [en, ko]) {
      for (const key of ["title", "body", "home"] as const) expect(m.notFound[key].length).toBeGreaterThan(0);
    }
    expect(ko.notFound.title).not.toBe(en.notFound.title);
  });

  it("reads its text from the notFound messages", () => {
    expect(readFileSync(join(__dirname, "../../app/not-found.tsx"), "utf8")).toContain('useTranslations("notFound")');
  });
});
