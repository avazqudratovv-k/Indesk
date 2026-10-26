import { describe, expect, it } from "vitest";
import { clone, fixtures } from "./fixtures";
import { parseReportDetail } from "./parse";

describe("parseReportDetail", () => {
  it("maps an answered report", () => {
    const bundle = parseReportDetail(fixtures.answered);
    expect(bundle).not.toBeNull();
    expect(bundle!.report).toMatchObject({ title: "Gangnam has the most boardings", confidence: "high", verified_count: 3, total_claims: 3, mode: "ask" });
    expect(bundle!.claims.map((claim) => claim.status)).toEqual(["verified", "verified", "verified"]);
    expect(bundle!.evidence[0]).toMatchObject({ ref: "D1", type: "table", location: "rows 1–4079" });
    expect(bundle!.report.summary_json.top_rows?.[0]).toEqual({ label: "Gangnam", value: "412,300", status: "verified" });
  });

  it("keeps the unverified claims of a partial report with their notes", () => {
    const bundle = parseReportDetail(fixtures.partial)!;
    expect(bundle.report.verified_count).toBe(2);
    expect(bundle.claims[1]).toMatchObject({ status: "unverified", evidence_refs: ["D1", "U1"] });
    expect(bundle.evidence.filter((item) => item.type === "critic_note").map((item) => item.payload.reason)).toEqual(["ranking_unchecked", "number_mismatch"]);
    expect(bundle.report.summary_json.top_rows?.map((row) => row.status)).toEqual(["verified", "flagged", "flagged", "verified"]);
  });

  it("accepts zero verified (0 of N, low)", () => {
    const bundle = parseReportDetail(fixtures.zero)!;
    expect(bundle.report).toMatchObject({ verified_count: 0, total_claims: 3, confidence: "low" });
  });

  it("accepts a report with no claims and no confidence", () => {
    const bundle = parseReportDetail(fixtures.empty)!;
    expect(bundle.claims).toEqual([]);
    expect(bundle.report.confidence).toBeNull();
    expect(bundle.report.total_claims).toBe(0);
  });

  it("turns an unknown confidence into null and an unknown claim status into unverified", () => {
    expect(parseReportDetail(fixtures.unknown)!.report.confidence).toBeNull();
    const raw = clone(fixtures.answered) as unknown as { claims: { status: string }[] };
    raw.claims[0].status = "brand_new";
    expect(parseReportDetail(raw)!.claims[0].status).toBe("unverified");
  });

  it("never keeps the code of a table (v1 shows none)", () => {
    const raw = clone(fixtures.answered) as unknown as { evidence: { payload: Record<string, unknown> }[] };
    raw.evidence[0].payload.code = "import os; os.system('x')";
    expect(parseReportDetail(raw)!.evidence[0].payload).not.toHaveProperty("code");
  });

  it("keeps Korean names with parentheses in labels and cells", () => {
    const bundle = parseReportDetail(fixtures.korean)!;
    expect(bundle.report.summary_json.top_rows?.[0].label).toBe("잠실(송파구청)");
    expect((bundle.evidence[0].payload.table as { rows: string[][] }).rows[0][0]).toBe("잠실(송파구청)");
  });

  it("cleans the text of every field", () => {
    const bundle = parseReportDetail(fixtures.html)!;
    expect(bundle.claims[2].text).toBe("bidi abc and zerowidth");
    expect(bundle.claims[1].text.length).toBeLessThanOrEqual(600);
    expect(bundle.claims[0].text).toContain("<script>");
  });

  it.each([
    ["not an object", null],
    ["an array", []],
    ["no claims list", { report: {}, evidence: [] }],
    ["a report without an id", (() => { const r = clone(fixtures.answered) as unknown as { report: Record<string, unknown> }; delete r.report.id; return r; })()],
    ["more verified than total", (() => { const r = clone(fixtures.answered) as unknown as { report: Record<string, unknown> }; r.report.verified_count = 9; return r; })()],
    ["a claim without text", (() => { const r = clone(fixtures.answered) as unknown as { claims: Record<string, unknown>[] }; r.claims[0].text = ""; return r; })()],
    ["an evidence ref that is not a ref", (() => { const r = clone(fixtures.answered) as unknown as { evidence: Record<string, unknown>[] }; r.evidence[0].ref = "../x"; return r; })()],
  ])("rejects %s", (_name, raw) => {
    expect(parseReportDetail(raw)).toBeNull();
  });
});
