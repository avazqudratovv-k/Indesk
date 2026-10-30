import type { NotAnswerable } from "@/lib/run/live/types";

type Translate = (key: string, values?: Record<string, string | number>) => string;

export type NaCopy = { head: string; body: string | null; containsLabel: string; contains: string | null };

// The words of a Not answerable card, built only from message keys and the checked facts. A fact that is absent leaves
// its sentence out; if the fact a headline needs is absent, the generic Not answerable wording is used instead.
export function notAnswerableCopy(na: NotAnswerable, t: Translate): NaCopy {
  const { reason, facts } = na;
  const generic = { head: t("reasons.notAnswerable.head"), body: t("reasons.notAnswerable.body") };
  const k = (key: string) => `real.na.${key}`;
  let head: string = generic.head;
  let body: string | null = null;

  if (reason === "csv_period") {
    if (facts.askedYear !== undefined) head = t(k("csv_period.head"), { year: String(facts.askedYear) });
    else body = generic.body;
    if (facts.timeColumn !== undefined && facts.yearMin !== undefined && facts.yearMax !== undefined) {
      body = t(k("csv_period.body"), { column: facts.timeColumn, min: String(facts.yearMin), max: String(facts.yearMax) });
    }
  } else if (reason === "csv_no_rows") {
    head = t(k("csv_no_rows.head"));
    body = facts.rowCount !== undefined ? t(k("csv_no_rows.body"), { rows: facts.rowCount }) : null;
  } else if (reason === "csv_missing_column") {
    // The column name is the user's own word from the question; without it the generic wording stays.
    if (facts.askedColumn !== undefined) {
      head = t(k("csv_missing_column.head"), { column: facts.askedColumn });
      body = t(k("csv_missing_column.body"));
    } else body = generic.body;
  } else if (reason === "pdf_no_match") {
    head = t(k("pdf_no_match.head"));
    body = facts.pageCount !== undefined ? t(k("pdf_no_match.body"), { pages: facts.pageCount }) : null;
  } else if (reason === "pdf_not_in_passages") {
    head = t(k("pdf_not_in_passages.head"));
    const searched = facts.searchedPages ?? [];
    const checked = searched.length > 0 ? t(k("pdf_not_in_passages.checked"), { pages: searched.join(", ") }) : t(k("pdf_not_in_passages.checkedNoPages"));
    body = facts.pageCount !== undefined ? `${checked} ${t(k("pdf_not_in_passages.ofPages"), { pages: facts.pageCount })}` : checked;
  } else if (facts.pageCount !== undefined) {
    head = t(k("pdf_page_range.head"), { pages: facts.pageCount });
    body = facts.askedPage !== undefined ? t(k("pdf_page_range.body"), { asked: facts.askedPage }) : null;
  } else {
    body = generic.body;
  }

  return { head, body, containsLabel: t(k("containsLabel")), contains: contains(na, t) };
}

// "What the file contains": a PDF says its pages, a CSV its rows and columns. Absent facts are left out.
function contains({ reason, facts }: NotAnswerable, t: Translate): string | null {
  if (reason.startsWith("pdf_")) {
    if (facts.pageCount === undefined) return null;
    if (facts.pagesWithText === undefined) return t("real.na.pdfPages", { pages: facts.pageCount });
    return t("real.na.pdfPagesText", { pages: facts.pageCount, withText: facts.pagesWithText });
  }
  const columns = facts.columns && facts.columns.length > 0 ? facts.columns.join(", ") : null;
  if (facts.rowCount !== undefined && columns) return t("real.na.csvRowsColumns", { rows: facts.rowCount, columns });
  if (facts.rowCount !== undefined) return t("real.na.csvRows", { rows: facts.rowCount });
  return columns ? t("real.na.csvColumns", { columns }) : null;
}
