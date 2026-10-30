import { describe, expect, it } from "vitest";
import { endCard, usesNoFreeRun } from "./reasons";
import { parseDone, parseNotAnswerable, parseRunSnapshot } from "./parse";
import { OUTCOMES } from "./types";

const csvPeriod = {
  reason: "csv_period",
  facts: { row_count: 4079, columns: ["date", "station", "riders"], time_column: "date", year_min: 2019, year_max: 2025, asked_year: 2015 },
  suggestions: [
    { text: "Ridership per year in this file?", kind: "csv_trend" },
    { text: "Which station has the most riders?", kind: "csv_rank" },
  ],
};

describe("parseNotAnswerable", () => {
  it("reads a valid object into camelCase facts and suggestions", () => {
    expect(parseNotAnswerable(csvPeriod)).toEqual({
      reason: "csv_period",
      facts: { rowCount: 4079, columns: ["date", "station", "riders"], timeColumn: "date", yearMin: 2019, yearMax: 2025, askedYear: 2015 },
      suggestions: [
        { text: "Ridership per year in this file?", kind: "csv_trend" },
        { text: "Which station has the most riders?", kind: "csv_rank" },
      ],
    });
  });

  it("accepts every known reason, empty facts and no suggestions", () => {
    for (const reason of ["pdf_no_match", "pdf_not_in_passages", "pdf_page_range", "csv_period", "csv_no_rows", "csv_missing_column"]) {
      expect(parseNotAnswerable({ reason, facts: {}, suggestions: [] })).toEqual({ reason, facts: {}, suggestions: [] });
    }
    expect(parseNotAnswerable({ reason: "csv_no_rows", facts: { row_count: 3 } })?.suggestions).toEqual([]);
  });

  it("drops an unknown reason or an unknown suggestion kind", () => {
    expect(parseNotAnswerable({ ...csvPeriod, reason: "because" })).toBeNull();
    expect(parseNotAnswerable({ ...csvPeriod, suggestions: [{ text: "x", kind: "csv_magic" }] })).toBeNull();
  });

  it.each([
    ["a string for a count", { ...csvPeriod, facts: { row_count: "4079" } }],
    ["a fractional page", { reason: "pdf_page_range", facts: { page_count: 2.5 } }],
    ["a negative number", { reason: "pdf_page_range", facts: { page_count: -1 } }],
    ["columns that are not a list", { ...csvPeriod, facts: { columns: "a,b" } }],
    ["a number as a column name", { ...csvPeriod, facts: { columns: [1] } }],
    ["facts that are not an object", { ...csvPeriod, facts: [] }],
    ["suggestions that are not a list", { ...csvPeriod, suggestions: "ask me" }],
    ["a suggestion without text", { ...csvPeriod, suggestions: [{ kind: "csv_rank" }] }],
    ["not an object", "csv_period"],
    ["null", null],
  ])("drops %s", (_name, value) => {
    expect(parseNotAnswerable(value)).toBeNull();
  });

  it("drops over-long strings and over-long lists", () => {
    expect(parseNotAnswerable({ ...csvPeriod, suggestions: [{ text: "x".repeat(201), kind: "csv_rank" }] })).toBeNull();
    expect(parseNotAnswerable({ ...csvPeriod, facts: { columns: ["c".repeat(81)] } })).toBeNull();
    expect(parseNotAnswerable({ ...csvPeriod, facts: { columns: Array.from({ length: 9 }, (_, i) => `c${i}`) } })).toBeNull();
    expect(parseNotAnswerable({ reason: "pdf_not_in_passages", facts: { searched_pages: [1, 2, 3, 4, 5, 6, 7, 8, 9] } })).toBeNull();
    expect(parseNotAnswerable({ ...csvPeriod, suggestions: [...csvPeriod.suggestions, csvPeriod.suggestions[0]] })).toBeNull();
  });

  it("reads asked_column (at most 80 characters) for csv_missing_column", () => {
    const base = { reason: "csv_missing_column", facts: { row_count: 14, columns: ["station"], asked_column: "revenue total" }, suggestions: [] };
    expect(parseNotAnswerable(base)?.facts).toEqual({ rowCount: 14, columns: ["station"], askedColumn: "revenue total" });
    expect(parseNotAnswerable({ ...base, facts: { asked_column: "c".repeat(80) } })?.facts.askedColumn).toHaveLength(80);
    expect(parseNotAnswerable({ ...base, facts: { asked_column: "c".repeat(81) } })).toBeNull();
    expect(parseNotAnswerable({ ...base, facts: { asked_column: 5 } })).toBeNull();
  });

  it("keeps markup as plain text and removes control and direction characters", () => {
    const na = parseNotAnswerable({ reason: "csv_no_rows", facts: { columns: ["<b>x</b>‮​ y"] }, suggestions: [] });
    expect(na?.facts.columns).toEqual(["<b>x</b> y"]);
  });
});

describe("not_answerable on the done event and the run view", () => {
  const id = "123e4567-e89b-12d3-a456-426614174000";

  it("is kept on a not_answerable done event and left out when invalid", () => {
    expect(parseDone({ outcome: "not_answerable", reason: null, report_id: null, not_answerable: csvPeriod })?.notAnswerable?.reason).toBe("csv_period");
    expect(parseDone({ outcome: "not_answerable", not_answerable: { ...csvPeriod, reason: "nope" } })).toEqual({ outcome: "not_answerable", reason: null, reportId: null });
    expect(parseDone({ outcome: "not_answerable", not_answerable: null })).toEqual({ outcome: "not_answerable", reason: null, reportId: null });
  });

  it("is ignored for other outcomes", () => {
    expect(parseDone({ outcome: "failed", not_answerable: csvPeriod })).toEqual({ outcome: "failed", reason: null, reportId: null });
  });

  it("is kept on the run snapshot", () => {
    const snapshot = parseRunSnapshot({ id, status: "finished", outcome: "not_answerable", not_answerable: csvPeriod, steps: [] });
    expect(snapshot?.notAnswerable?.facts.askedYear).toBe(2015);
    expect(parseRunSnapshot({ id, status: "finished", outcome: "not_answerable", not_answerable: 5, steps: [] })?.notAnswerable).toBeUndefined();
  });
});

describe("the free run tag", () => {
  it("is shown for not_answerable and needs_better_input, and for no other outcome", () => {
    const expected: Record<(typeof OUTCOMES)[number], boolean> = { answered: false, partial: false, not_answerable: true, needs_better_input: true, rejected: false, failed: false };
    for (const outcome of OUTCOMES) {
      expect(usesNoFreeRun(outcome)).toBe(expected[outcome]);
      const card = endCard(outcome, null);
      expect(card.kind === "problem" && card.noFreeRun).toBe(expected[outcome]);
    }
  });
});
