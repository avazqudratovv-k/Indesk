import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { toRealEvidenceView } from "@/lib/report/real/evidence-view";

import { clone, fixtures, type FixtureName } from "@/lib/report/real/fixtures";
import { parseReportDetail } from "@/lib/report/real/parse";

import EvidencePanel from "./EvidencePanel";
import ReportView, { type RealInfo } from "./ReportView";

type Locale = "en" | "ko";

function page(node: React.ReactNode, locale: Locale = "en"): string {
  return renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko}>
      {node}
    </NextIntlClientProvider>,
  );
}

function report(name: FixtureName, real: RealInfo = { lang: "en", note: null }, locale: Locale = "en"): string {
  return page(<ReportView bundle={parseReportDetail(fixtures[name])!} real={real} />, locale);
}


describe("a PDF report", () => {
  it("renders without top_rows: no rows, no chart, the in-short line and the stamp", () => {
    for (const locale of ["en", "ko"] as const) {
      const html = report("pdf", { lang: locale, note: null }, locale);
      expect(html).toContain("2,450,051");
      expect(html).not.toContain(locale === "en" ? "computed data" : "계산된 데이터");
    }
  });

  it("evidence panel shows the quote as plain text and a source line with file, page and similarity", () => {
    const bundle = parseReportDetail(fixtures.pdf)!;
    const say = (key: string, values?: Record<string, string | number>) => key + JSON.stringify(values ?? {});
    const view = toRealEvidenceView(bundle.evidence[0], say);
    expect(view.quote).toBe("Gangnam station recorded 2,450,051 boardings in the month.");
    expect(view.metaText).toBe('seoul_subway_2026-09.pdf · evidence.page{"n":4} · evidence.similarity{"value":0.83}');
    const html = page(<EvidencePanel view={toRealEvidenceView(bundle.evidence[0], (key) => key)} variant="aside" />);
    expect(html).toContain("<blockquote");
  });

  it("a hostile quote is escaped, never markup", () => {
    const raw = clone(fixtures.pdf);
    raw.evidence[0].payload.quote = "<img src=x onerror=alert(1)>";
    const bundle = parseReportDetail(raw)!;
    const html = page(<EvidencePanel view={toRealEvidenceView(bundle.evidence[0], () => "t")} variant="aside" />);
    expect(html).not.toContain("<img");
  });
});
