import { describe, expect, it } from "vitest";
import { IntlErrorCode, createTranslator } from "next-intl";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { clone, fixtures } from "./fixtures";
import { claimReason, toRealEvidenceView } from "./evidence-view";
import { parseReportDetail } from "./parse";

function sayFor(locale: "en" | "ko") {
  const t = createTranslator({ locale, messages: locale === "en" ? en : ko, namespace: "report", onError: (error) => { if (error.code === IntlErrorCode.MISSING_MESSAGE) throw error; } });
  return t as unknown as (key: string, values?: Record<string, string | number>) => string;
}

describe("toRealEvidenceView", () => {
  it("builds the D1 panel from codes: title, method, rows used and a translated source line", () => {
    const bundle = parseReportDetail(fixtures.answered)!;
    const view = toRealEvidenceView(bundle.evidence[0], sayFor("en"));
    expect(view).toMatchObject({ ref: "D1", title: "Computed table", body: "Ranked from your file. Used 4,079 rows", metaText: "pandas · seoul_subway_2026-09.csv · Rows 1–4,079" });
    expect(view.table?.headers).toEqual(["Station", "Boardings"]);
    expect(view.code).toBeNull();
  });

  it("speaks Korean for the same data", () => {
    const view = toRealEvidenceView(parseReportDetail(fixtures.answered)!.evidence[0], sayFor("ko"));
    expect(view.body).toBe("파일에서 순위를 계산했습니다. 4,079행 사용");
    expect(view.metaText).toContain("1–4,079행");
  });

  it("builds a critic note from its reason and shows no source line", () => {
    const bundle = parseReportDetail(fixtures.partial)!;
    const note = bundle.evidence.find((item) => item.ref === "U1")!;
    expect(toRealEvidenceView(note, sayFor("en"))).toMatchObject({ title: "Ranking not proven", metaText: null, table: null });
  });

  it("falls back to neutral text for unknown codes and never shows a raw one", () => {
    const bundle = parseReportDetail(fixtures.unknown)!;
    const say = sayFor("en");
    const d1 = toRealEvidenceView(bundle.evidence[0], say);
    const note = toRealEvidenceView(bundle.evidence[1], say);
    expect(d1.body).toBe("Computed from your file. Used 4,079 rows");
    expect(d1.metaText).toBe("seoul_subway_2026-09.csv");
    expect(note).toMatchObject({ title: "Could not be verified", body: "This claim could not be checked." });
    for (const text of [d1.title, d1.body, d1.metaText ?? "", note.title, note.body]) expect(text).not.toMatch(/future|somewhere|run_python/);
  });

  it("leaves out an unusable table", () => {
    const raw = clone(fixtures.answered) as unknown as { evidence: { payload: Record<string, unknown> }[] };
    raw.evidence[0].payload.table = { headers: "x", rows: 3 };
    expect(toRealEvidenceView(parseReportDetail(raw)!.evidence[0], sayFor("en")).table).toBeNull();
  });
});

describe("claimReason", () => {
  it("gives the title of the claim's critic note, or null", () => {
    const bundle = parseReportDetail(fixtures.partial)!;
    const say = sayFor("en");
    expect(claimReason(bundle.claims[1].evidence_refs, bundle.evidence, say)).toBe("Ranking not proven");
    expect(claimReason(bundle.claims[2].evidence_refs, bundle.evidence, say)).toBe("Number does not match");
    expect(claimReason(bundle.claims[0].evidence_refs, bundle.evidence, say)).toBeNull();
  });

  it("uses the neutral title for an unknown reason", () => {
    const bundle = parseReportDetail(fixtures.unknown)!;
    expect(claimReason(bundle.claims[0].evidence_refs, bundle.evidence, sayFor("en"))).toBe("Could not be verified");
  });
});
