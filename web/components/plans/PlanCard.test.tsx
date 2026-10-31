import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import PlanCard from "./PlanCard";

const limits = { max_file_mb: 5, csv_rows: 20000, pdf_pages: 30, runs_per_day: 10 };
const offers = [
  { plan: "free", runs: 3, price: 0, period: "forever", popular: false },
  { plan: "pro", runs: 50, price: 12000, period: "month", popular: true },
  { plan: "payg", runs: 20, price: 6500, period: "once", popular: false },
] as const;

function render(locale: "en" | "ko", index: number) {
  return renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko}>
      <PlanCard offer={offers[index]} limits={limits} signedIn={false} current={false} onChoose={() => {}} />
    </NextIntlClientProvider>,
  );
}

describe("plan cards list the same three true limits", () => {
  it.each([0, 1, 2])("en card %i shows file size, CSV rows and PDF pages", (i) => {
    const html = render("en", i);
    expect(html).toContain("Files up to 5 MB each");
    expect(html).toContain("CSV up to 20,000 rows");
    expect(html).toContain("PDF up to 30 pages");
  });

  it.each([0, 1, 2])("ko card %i shows the three limits", (i) => {
    const html = render("ko", i);
    expect(html).toContain("파일당 최대 5MB");
    expect(html).toContain("CSV 최대 20,000행");
    expect(html).toContain("PDF 최대 30쪽");
  });

  it("each card keeps its own runs line", () => {
    expect(render("en", 1)).toContain("50 runs per month");
    expect(render("en", 2)).toContain("20 runs, never expire");
  });
});
