import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import TeamReady from "./TeamReady";

function names(withHound: boolean, locale: "en" | "ko" = "en"): string[] {
  const html = renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko}>
      <TeamReady withHound={withHound} />
    </NextIntlClientProvider>,
  );
  return [...html.matchAll(/<li[^>]*>.*?>([^<>]+)<\/li>/g)].map((m) => m[1]);
}

describe("the team strip in the Ask panel", () => {
  it("shows Owl, Beaver and Cat for a CSV and with nothing attached", () => {
    expect(names(false)).toEqual(["Owl", "Beaver", "Cat"]);
  });

  it("shows Owl, Hound and Cat for a PDF", () => {
    expect(names(true)).toEqual(["Owl", "Hound", "Cat"]);
  });

  it("is written in Korean too", () => {
    expect(names(true, "ko")).toHaveLength(3);
    expect(names(false, "ko")).toHaveLength(3);
  });
});
