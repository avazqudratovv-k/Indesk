import { describe, expect, it } from "vitest";
import { MAX_CSV_ROWS, MAX_FILE_BYTES, MAX_PDF_CHARS, MAX_PDF_PAGES } from "@/lib/limits";
import { ASK_ACCEPT, checkFile, SLOT_MAX } from "./validate";

const csv = (name: string) => new File(["a,b\n1,2"], name, { type: "text/csv" });
const base = { slot: "files" as const, takenNames: new Set<string>(), count: 0, partnerKind: null, csvOnly: true };

describe("Ask takes exactly one CSV", () => {
  it("allows one file in the Ask slot", () => {
    expect(SLOT_MAX.files).toBe(1);
    expect(checkFile(csv("a.csv"), base)).toBeNull();
  });

  it("turns a second file away with slotFull and does not replace the first", () => {
    expect(checkFile(csv("b.csv"), { ...base, count: 1, takenNames: new Set(["a.csv"]) })).toBe("slotFull");
  });

  it("checks a drop of two files as a whole: the first is accepted, the second is not", () => {
    const taken = new Set<string>();
    expect(checkFile(csv("a.csv"), { ...base, takenNames: taken, count: 0 })).toBeNull();
    taken.add("a.csv");
    expect(checkFile(csv("b.csv"), { ...base, takenNames: taken, count: 1 })).toBe("slotFull");
  });
});

const pdf = (name: string, type = "application/pdf") => new File(["%PDF-1.7"], name, { type });
const png = (name: string) => new File(["x"], name, { type: "image/png" });

describe("Ask takes one CSV or one PDF", () => {
  it("accepts a PDF in the Ask slot", () => {
    expect(checkFile(pdf("report.pdf"), base)).toBeNull();
  });

  it("refuses images with csvOnly (\"Images are not available yet\")", () => {
    expect(checkFile(png("chart.png"), base)).toBe("csvOnly");
  });

  it("refuses a renamed file whose type does not match its extension", () => {
    expect(checkFile(pdf("report.pdf", "text/csv"), base)).toBe("type");
  });

  it("turns a PDF away when a CSV is already there", () => {
    expect(checkFile(pdf("report.pdf"), { ...base, count: 1, takenNames: new Set(["a.csv"]) })).toBe("slotFull");
  });

  it("checks only type, size and name, never content", () => {
    expect(checkFile(new File([], "empty.pdf", { type: "application/pdf" }), base)).toBe("empty");
    expect(checkFile(pdf("x".repeat(256) + ".pdf"), base)).toBe("nameTooLong");
  });

  it("lists the same kinds in the accept attribute", () => {
    expect(ASK_ACCEPT).toContain(".pdf");
    expect(ASK_ACCEPT).toContain(".csv");
    expect(ASK_ACCEPT).not.toContain("png");
  });

  it("holds the server limits for copy", () => {
    expect([MAX_CSV_ROWS, MAX_PDF_PAGES, MAX_PDF_CHARS, MAX_FILE_BYTES]).toEqual([20000, 30, 150000, 5 * 1024 * 1024]);
  });
});
