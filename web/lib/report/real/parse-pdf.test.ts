import { describe, expect, it } from "vitest";
import { clone, fixtures } from "./fixtures";
import { parseReportDetail } from "./parse";

describe("a PDF report", () => {
  it("keeps the document quote, location and value of a claim and the passage evidence", () => {
    const bundle = parseReportDetail(fixtures.pdf)!;
    expect(bundle.claims[0]).toMatchObject({ origin: "document", doc_quote: "Gangnam station recorded 2,450,051 boardings in the month.", doc_location: "p4", doc_value: "2,450,051" });
    expect(bundle.evidence[0].payload).toMatchObject({ page: 4, similarity: 0.83, quote: "Gangnam station recorded 2,450,051 boardings in the month." });
    expect(bundle.evidence[0].payload).not.toHaveProperty("code");
  });

  it("has no top_rows and still parses; a long or odd quote is cut and cleaned", () => {
    expect(parseReportDetail(fixtures.pdf)!.report.summary_json.top_rows).toBeUndefined();
    const raw = clone(fixtures.pdf);
    raw.claims[0].doc_quote = "x".repeat(900) + "\u202e";
    raw.claims[0].origin = "bogus";
    raw.evidence[0].payload.similarity = 5;
    const bundle = parseReportDetail(raw)!;
    expect(bundle.claims[0].doc_quote!.length).toBeLessThanOrEqual(600);
    expect(bundle.claims[0].doc_quote).not.toContain("\u202e");
    expect(bundle.claims[0].origin).toBe("answer");
    expect(bundle.evidence[0].payload).not.toHaveProperty("similarity");
  });
});
