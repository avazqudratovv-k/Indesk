import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider, useTranslations } from "next-intl";
import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { claimReason, toRealEvidenceView } from "@/lib/report/real/evidence-view";
import type { ReportBundle } from "@/lib/report/get-report";
import { fixtures, type FixtureName } from "@/lib/report/real/fixtures";
import { parseReportDetail } from "@/lib/report/real/parse";
import type { Evidence } from "@/lib/types";
import ClaimList from "./ClaimList";
import Glossary from "./Glossary";
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

// The detailed view is client state, so the list is rendered directly with the props ReportView gives it.
function Claims({ bundle }: { bundle: ReportBundle }) {
  const t = useTranslations("report");
  const say = t as unknown as (key: string, values?: Record<string, string | number>) => string;
  return (
    <ClaimList
      claims={bundle.claims}
      evidence={bundle.evidence}
      showUnverified
      onShowUnverified={() => undefined}
      selectedRef="D1"
      openClaim={null}
      onPick={() => undefined}
      viewOf={(item: Evidence) => toRealEvidenceView(item, say)}
      reasonOf={(claim) => claimReason(claim.evidence_refs, bundle.evidence, say)}
    />
  );
}

function claims(name: FixtureName, locale: Locale = "en"): string {
  return page(<Claims bundle={parseReportDetail(fixtures[name])!} />, locale);
}

describe("a real report (Simple view)", () => {
  it("answered: stamp, rows that match, high confidence, no example banner or report number", () => {
    const html = report("answered");
    expect(html).toContain("Verified");
    expect(html).toContain("3 of 3");
    expect(html).toContain("High confidence");
    expect(html).toContain("✓ matches");
    expect(html).not.toContain("! not proven");
    expect(html).not.toContain("Example report");
    expect(html).not.toMatch(/Report No/i);
    expect(html).toContain("Final answer");
  });

  it("partial: counts, marks not-proven rows and uses the real wording for the open ones", () => {
    const html = report("partial");
    expect(html).toContain("2 of 4");
    expect(html).toContain("Medium confidence");
    expect(html).toContain("! not proven");
    expect(html).toContain("2 could not be verified and are marked.");
    expect(html).not.toContain("only ideas");
  });

  it("zero verified: 0 of N, low confidence, nothing shown as matching", () => {
    const html = report("zero");
    expect(html).toContain("0 of 3");
    expect(html).toContain("Low confidence");
    expect(html).not.toContain("✓ matches");
  });

  it("no claims: no stamp, no confidence card, the no-claims text", () => {
    const html = report("empty");
    expect(html).toContain("This report has no claims to show.");
    expect(html).not.toContain('role="img"');
    expect(html).not.toContain("How sure are we?");
    expect(html).not.toContain("confidence");
  });

  it("an unknown confidence shows no confidence at all", () => {
    const html = report("unknown");
    expect(html).not.toContain("How sure are we?");
    expect(html).not.toMatch(/very_high|very high/i);
  });

  it("has no chart, no code and no Share, Style or follow-up control", () => {
    const html = report("answered");
    expect(html).not.toContain("Growth since");
    expect(html).not.toMatch(/<pre|Share<|Style &amp; download|Ask more/);
    expect(html).toContain("Sharing, download and follow-up questions come in a later version.");
  });

  it("shows the language note only when told to, and never says it is a translation", () => {
    expect(report("answered", { lang: "en", note: null })).not.toContain("The text of this report");
    const note = report("answered", { lang: "en", note: "en" }, "ko");
    expect(note).toContain("이 보고서의 본문은 영어로 작성되었습니다.");
    expect(note).not.toMatch(/번역|translat/i);
    expect(report("answered", { lang: "ko", note: "ko" }, "en")).toContain("The text of this report is in Korean.");
    expect(report("answered", { lang: "en", note: "en" }, "ko")).not.toMatch(/translat|번역/i);
  });

  it("marks the prose with its own language and leaves the labels alone", () => {
    const html = report("answered", { lang: "en", note: null }, "ko");
    expect(html).toMatch(/<h1[^>]*lang="en"[^>]*>Gangnam has the most boardings/);
    expect(html).not.toMatch(/<h2[^>]*lang=/);
    expect(report("answered", { lang: null, note: null })).not.toMatch(/ lang="/);
  });

  it("renders every server text as plain text: markup is escaped and nothing becomes a link", () => {
    const html = report("html");
    expect(html).not.toContain("<script");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<b>Title");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toMatch(/href="https?:/);
    expect(html).not.toMatch(/<a[ >]/);
  });

  it("keeps a Korean report with names in parentheses intact", () => {
    const html = report("korean", { lang: "ko", note: null }, "ko");
    expect(html).toContain("잠실(송파구청)");
    expect(html).toContain("2개 중 1개");
  });
});

describe("a real report (Detailed view)", () => {
  it("shows the reason under each unverified claim, from the closed code", () => {
    const html = claims("partial");
    // Each reason appears once, as the line under its claim (the panels are closed).
    expect(html.split("Ranking not proven")).toHaveLength(2);
    expect(html.split("Number does not match")).toHaveLength(2);
    expect(html.split("Unverified")).toHaveLength(3);
    expect(html).not.toMatch(/ranking_unchecked|number_mismatch/);
  });

  it("shows zero verified with every claim marked and every reason given", () => {
    const html = claims("zero");
    expect(html).not.toContain(">Verified<");
    expect(html).toContain("Number does not match");
    expect(html).toContain("Ranking not proven");
  });

  it("falls back to neutral text for an unknown reason", () => {
    const html = claims("unknown");
    expect(html).toContain("Could not be verified");
    expect(html).not.toMatch(/future_reason|future_method/);
  });

  it("wraps long and escaped claim text instead of linking it", () => {
    const html = claims("html");
    expect(html).not.toContain("<script");
    expect(html).not.toMatch(/<a[ >]/);
  });

  it("the evidence panel shows a Korean-station table as plain cells", () => {
    const bundle = parseReportDetail(fixtures.korean)!;
    function Panel() {
      const t = useTranslations("report");
      const say = t as unknown as (key: string, values?: Record<string, string | number>) => string;
      return <EvidencePanel view={toRealEvidenceView(bundle.evidence[0], say)} variant="aside" />;
    }
    const html = page(<Panel />, "ko");
    expect(html).toContain("<td>잠실(송파구청)</td>");
    expect(html).toContain("<th scope=\"col\">역명</th>");
    expect(html).toContain("파일에서 순위를 계산했습니다");
    expect(html).toContain("pandas");
    expect(html).not.toMatch(/run_python/);
  });

  it("large values are shown exactly as the server formatted them", () => {
    const bundle = parseReportDetail(fixtures.html)!;
    function Panel() {
      const t = useTranslations("report");
      const say = t as unknown as (key: string, values?: Record<string, string | number>) => string;
      return <EvidencePanel view={toRealEvidenceView(bundle.evidence[0], say)} variant="inline" />;
    }
    expect(page(<Panel />)).toContain("1,234,567,890,123");
  });
});

describe("the words explained", () => {
  it("a real report explains verified and unverified against the computed table", () => {
    const html = page(<Glossary real />);
    expect(html).toContain("matches the computed table");
    expect(html).not.toContain("found the quote in your files");
    expect(page(<Glossary />)).toContain("found the quote in your files");
  });
});
