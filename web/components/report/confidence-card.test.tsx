import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { fixtures } from "@/lib/report/real/fixtures";
import { parseReportDetail } from "@/lib/report/real/parse";
import ConfidenceCard from "./ConfidenceCard";

type Locale = "en" | "ko";
const pdf = parseReportDetail(fixtures.pdf)!;
const csv = parseReportDetail(fixtures.answered)!;

function card(bundle: typeof pdf, counts: { total: number; verified: number }, locale: Locale): string {
  const report = { ...bundle.report, confidence: "high" as const, total_claims: counts.total, verified_count: counts.verified };
  return renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko}>
      <ConfidenceCard report={report} claims={bundle.claims} real />
    </NextIntlClientProvider>,
  );
}

describe("the confidence note of a PDF report", () => {
  it("says the statements match quotes in the document, never computed data", () => {
    expect(card(pdf, { total: 3, verified: 3 }, "en")).toContain("We checked 3 statements. 3 match quotes in the document.");
    expect(card(pdf, { total: 3, verified: 3 }, "en")).not.toContain("computed");
    expect(card(pdf, { total: 3, verified: 3 }, "ko")).toContain("진술 3개를 확인했습니다. 3개는 문서의 인용문과 일치합니다.");
  });

  it("uses singular and plural forms in English", () => {
    expect(card(pdf, { total: 1, verified: 1 }, "en")).toContain("We checked 1 statement. 1 matches a quote in the document.");
    expect(card(pdf, { total: 2, verified: 1 }, "en")).toContain("We checked 2 statements. 1 matches a quote in the document. 1 could not be verified and is marked.");
  });

  it("reads 1개 in Korean", () => {
    expect(card(pdf, { total: 1, verified: 1 }, "ko")).toContain("진술 1개를 확인했습니다. 1개는 문서의 인용문과 일치합니다.");
  });
});

describe("the confidence note of a CSV report", () => {
  it("keeps the computed-data copy with proper plural forms", () => {
    expect(card(csv, { total: 1, verified: 1 }, "en")).toContain("We checked 1 statement. 1 matches the computed data.");
    expect(card(csv, { total: 4, verified: 3 }, "en")).toContain("We checked 4 statements. 3 match the computed data. 1 could not be verified and is marked.");
    expect(card(csv, { total: 1, verified: 1 }, "ko")).toContain("진술 1개를 확인했습니다. 1개는 계산된 데이터와 일치합니다.");
    expect(card(csv, { total: 4, verified: 3 }, "ko")).toContain("진술 4개를 확인했습니다. 3개는 계산된 데이터와 일치합니다.");
  });
});

describe("the evidence source line", () => {
  it("keeps p. and the page number together", () => {
    expect(en.report.evidence.page).toBe("p. {n, number}");
    expect(ko.report.evidence.page).toBe("{n, number}⁠쪽");
  });
});
