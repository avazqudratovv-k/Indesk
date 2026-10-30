import { renderToStaticMarkup } from "react-dom/server";
import { isValidElement, type ReactNode } from "react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import { endCard } from "@/lib/run/live/reasons";
import { initialRun } from "@/lib/run/live/reducer";
import type { NotAnswerable, Outcome } from "@/lib/run/live/types";
import RealRunView from "./RealRunView";
import RunEndCard from "./RunEndCard";

type Locale = "en" | "ko";
const messages = { en, ko };

function card(na: NotAnswerable | null, locale: Locale = "en", onAskInstead?: (text: string) => void, outcome: Outcome = "not_answerable"): string {
  return renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={messages[locale]}>
      <RunEndCard card={endCard(outcome, null)} reportId={null} notAnswerable={na} headingRef={null} onChange={() => undefined} onAskInstead={onAskInstead} />
    </NextIntlClientProvider>,
  );
}

const suggestions = [
  { text: "Ridership per year in this file?", kind: "csv_trend" as const },
  { text: "Which <station> has the most riders?", kind: "csv_rank" as const },
];

const csvPeriod: NotAnswerable = { reason: "csv_period", facts: { rowCount: 4079, columns: ["date", "station", "<i>riders</i>"], timeColumn: "date", yearMin: 2019, yearMax: 2025, askedYear: 2015 }, suggestions };
const csvNoRows: NotAnswerable = { reason: "csv_no_rows", facts: { rowCount: 120, columns: ["a", "b"] }, suggestions: [] };
const missing: NotAnswerable = { reason: "csv_missing_column", facts: { rowCount: 14, columns: ["station", "year", "riders"], askedColumn: "revenue total" }, suggestions: [] };
const missingUnnamed: NotAnswerable = { reason: "csv_missing_column", facts: { rowCount: 14, columns: ["station", "year", "riders"] }, suggestions: [] };
const pdfNoMatch: NotAnswerable = { reason: "pdf_no_match", facts: { pageCount: 12, pagesWithText: 10 }, suggestions: [{ text: "What is this document about?", kind: "pdf_about" }] };
const pdfPassages: NotAnswerable = { reason: "pdf_not_in_passages", facts: { pageCount: 12, pagesWithText: 12, searchedPages: [3, 5, 9] }, suggestions: [] };
const pdfRange: NotAnswerable = { reason: "pdf_page_range", facts: { pageCount: 4, askedPage: 9 }, suggestions: [{ text: "What is on page 2?", kind: "pdf_page" }] };

describe("Not answerable card, English", () => {
  it("csv_period names the year, the column and the range, and what the file holds", () => {
    const html = card(csvPeriod, "en", () => undefined);
    expect(html).toContain("The file does not cover 2015");
    expect(html).toContain("&#x27;date&#x27; holds data from 2019 to 2025.");
    expect(html).toContain("What the file contains");
    expect(html).toContain("4,079 rows, columns: date, station, &lt;i&gt;riders&lt;/i&gt;");
    expect(html).toContain("You could ask instead");
  });

  it("csv_no_rows", () => {
    const html = card(csvNoRows);
    expect(html).toContain("No rows matched your question");
    expect(html).toContain("The file has 120 rows.");
    expect(html).toContain("120 rows, columns: a, b");
    expect(html).not.toContain("You could ask instead");
  });

  it("csv_missing_column names the column the question asked for and lists the real ones", () => {
    const html = card(missing);
    expect(html).toContain("The file has no &#x27;revenue total&#x27; column");
    expect(html).toContain("Ask about one of the columns listed below.");
    expect(html).toContain("14 rows, columns: station, year, riders");
  });

  it("pdf_no_match mentions the page count and the pages with text", () => {
    const html = card(pdfNoMatch);
    expect(html).toContain("No passage in this document matches");
    expect(html).toContain("The document has 12 pages");
    expect(html).toContain("12 pages, 10 with text");
  });

  it("pdf_not_in_passages says it checked passages, never that it read pages", () => {
    const html = card(pdfPassages);
    expect(html).toContain("The document doesn&#x27;t answer this");
    expect(html).toContain("We checked the passages on pages 3, 5, 9 that best match your question. None answers it. The document has 12 pages.");
    expect(html).not.toMatch(/we read/i);
  });

  it("pdf_page_range", () => {
    const html = card(pdfRange);
    expect(html).toContain("The file has only 4 pages");
    expect(html).toContain("You asked about page 9.");
  });

  it("leaves out facts that are absent and keeps the Change question button", () => {
    const html = card({ reason: "pdf_no_match", facts: {}, suggestions: [] });
    expect(html).not.toContain("What the file contains");
    expect(html).toContain("Change question");
  });

  it("falls back to the generic card when there is no valid object", () => {
    const html = card(null);
    expect(html).toContain("The file doesn&#x27;t answer this question");
    expect(html).toContain("Try a question about what the file contains.");
    expect(html).not.toContain("What the file contains");
  });

  it("renders column names and suggestions as plain text", () => {
    const html = card(csvPeriod, "en", () => undefined);
    expect(html).not.toContain("<i>riders</i>");
    expect(html).toContain("Which &lt;station&gt; has the most riders?");
  });
});

describe("Not answerable card, Korean", () => {
  it("csv_period", () => {
    const html = card(csvPeriod, "ko", () => undefined);
    expect(html).toContain("이 파일에는 2015년 내용이 없습니다");
    expect(html).toContain("&#x27;date&#x27; 열에는 2019~2025 자료만 있습니다.");
    expect(html).toContain("파일에 들어 있는 내용");
    expect(html).toContain("4,079행, 열: date, station");
    expect(html).toContain("대신 이렇게 물어보세요");
    expect(html).toContain("무료 실행 미사용");
  });

  it("the other reasons", () => {
    expect(card(csvNoRows, "ko")).toContain("질문에 맞는 행이 없습니다");
    expect(card(csvNoRows, "ko")).toContain("파일에는 120행이 있습니다.");
    expect(card(pdfNoMatch, "ko")).toContain("질문에 맞는 내용이 문서에 없습니다");
    expect(card(pdfNoMatch, "ko")).toContain("12쪽, 그중 10쪽에 텍스트 있음");
    const passages = card(pdfPassages, "ko");
    expect(passages).toContain("이 문서에서는 답을 찾지 못했습니다");
    expect(passages).toContain("3, 5, 9쪽의 내용을 확인했지만");
    expect(passages).toContain("문서는 총 12쪽입니다.");
    expect(card(pdfRange, "ko")).toContain("이 파일은 4쪽까지만 있습니다");
    expect(card(pdfRange, "ko")).toContain("9쪽에 대해 물으셨습니다.");
  });

  it("csv_missing_column names the column in Korean", () => {
    const html = card(missing, "ko");
    expect(html).toContain("이 파일에는 &#x27;revenue total&#x27; 열이 없습니다");
    expect(html).toContain("아래에 나온 열 중에서 골라 물어보세요.");
  });

  it("a Korean question on an English-only file ends with the generic Korean headline and the real columns", () => {
    const html = card(missingUnnamed, "ko");
    expect(html).toContain(ko.workspace.reasons.notAnswerable.head);
    expect(html).toContain("14행, 열: station, year, riders");
    expect(html).not.toContain("열이 없습니다");
  });

  it("uses no 은(는) style particle markers", () => {
    expect(JSON.stringify(ko.workspace.real.na)).not.toMatch(/\(은\)|\(는\)|\(이\)|\(가\)|\(을\)|\(를\)/);
  });
});

describe("suggestion chips", () => {
  // The component is a plain function of its props except for useTranslations, so it is called directly with the
  // translations replaced, and the buttons are found in the element tree it returns.
  it("are buttons whose click hands the suggestion text to the page, and nothing else", async () => {
    vi.resetModules();
    vi.doMock("next-intl", () => ({ useTranslations: () => (key: string) => key }));
    const { default: Card } = await import("./RunEndCard");
    const asked: string[] = [];
    const tree = Card({ card: endCard("not_answerable", null), reportId: null, notAnswerable: csvPeriod, headingRef: null, onChange: () => asked.push("change"), onAskInstead: (text) => asked.push(text) });
    const buttons: { props: { onClick?: () => void; type?: string; children?: ReactNode } }[] = [];
    const walk = (node: ReactNode): void => {
      if (Array.isArray(node)) node.forEach(walk);
      else if (isValidElement(node)) {
        const element = node as unknown as { type: unknown; props: { children?: ReactNode; onClick?: () => void; type?: string } };
        if (element.type === "button") buttons.push(element);
        walk(element.props.children);
      }
    };
    walk(tree);
    const chips = buttons.filter((button) => button.props.type === "button" && suggestions.some((s) => button.props.children === s.text));
    expect(chips).toHaveLength(2);
    chips[1].props.onClick?.();
    expect(asked).toEqual(["Which <station> has the most riders?"]);
    vi.doUnmock("next-intl");
  });

  it("are shown only when the page can use them", () => {
    expect(card(csvPeriod, "en", () => undefined)).toContain("<button");
    expect(card(csvPeriod, "en")).not.toContain("You could ask instead");
  });
});

describe("the tag", () => {
  it("shows Doesn't use a free run for not_answerable and needs_better_input, in both languages", () => {
    expect(card(null, "en", undefined, "not_answerable")).toContain("Doesn&#x27;t use a free run");
    expect(card(null, "en", undefined, "needs_better_input")).toContain("Doesn&#x27;t use a free run");
    expect(card(null, "ko", undefined, "needs_better_input")).toContain("무료 실행 미사용");
    expect(card(null, "en", undefined, "failed")).not.toContain("use a free run");
  });
});

function view(outcome: Outcome, na?: NotAnswerable, locale: Locale = "en"): string {
  const run = { ...initialRun("123e4567-e89b-12d3-a456-426614174000", "Q?"), status: "finished" as const, done: { outcome, reason: outcome === "failed" ? "internal_error" : null, reportId: null, ...(na ? { notAnswerable: na } : {}) } };
  return renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={messages[locale]}>
      <RealRunView run={run} connection="live" onReconnect={() => undefined} onBack={() => undefined} onAskInstead={() => undefined} />
    </NextIntlClientProvider>,
  );
}

describe("the mark and the announcement follow the outcome", () => {
  const mark = (html: string) => html.match(/<span class="[^"]*mark[^"]*">([^<]*)<\/span>/)?.[1];
  const live = (html: string) => html.match(/role="status" aria-live="polite">([^<]*)</)?.[1];

  it("not_answerable is No answer / 답 없음, never Did not finish", () => {
    expect(mark(view("not_answerable"))).toBe("No answer");
    expect(mark(view("not_answerable", undefined, "ko"))).toBe("답 없음");
    expect(live(view("not_answerable", csvPeriod))).toBe("The run ended without an answer. The file does not cover 2015");
    expect(live(view("not_answerable"))).not.toContain("did not finish");
  });

  it("needs_better_input has its own warn mark and wording", () => {
    const html = view("needs_better_input");
    expect(mark(html)).toBe("Needs better input");
    expect(html).toMatch(/class="[^"]*mark[^"]*warn[^"]*"/);
    expect(live(html)).toBe("The run ended: the input needs to be better. We need a better input");
    expect(mark(view("needs_better_input", undefined, "ko"))).toBe("더 나은 입력 필요");
  });

  it("failed, rejected and busy keep Did not finish", () => {
    expect(mark(view("failed"))).toBe("Did not finish");
    expect(mark(view("rejected"))).toBe("Did not finish");
    expect(live(view("failed"))).toMatch(/^The run did not finish\./);
    expect(mark(view("failed", undefined, "ko"))).toBe("끝나지 않음");
  });
});
