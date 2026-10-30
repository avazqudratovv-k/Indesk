import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import type { FileStatus } from "@/lib/run/live/submit";
import FileSlot from "./FileSlot";

const item = { id: "f1", file: new File(["%PDF"], "report.pdf", { type: "application/pdf" }), kind: "pdf" as const };

function slot(status: FileStatus | undefined, locale: "en" | "ko" = "en"): string {
  return renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko}>
      <FileSlot slot="files" csvOnly items={[item]} errors={[]} statuses={status ? { f1: status } : undefined} locked onAdd={() => undefined} onRemove={() => undefined} />
    </NextIntlClientProvider>,
  );
}

const ready = (pagesWithoutText?: number): FileStatus => ({ state: "ready", expiresAt: 4_000_000_000_000, pagesWithoutText });

describe("pages without text note", () => {
  it("shows the neutral note when pages have no text", () => {
    expect(slot(ready(3))).toContain("3 pages have no text and can&#x27;t be searched.");
    expect(slot(ready(1))).toContain("1 page has no text");
  });

  it("shows nothing when the field is absent (CSV) or 0", () => {
    expect(slot(ready(undefined))).not.toContain("no text");
    expect(slot(ready(0))).not.toContain("no text");
    expect(slot(undefined)).not.toContain("no text");
  });

  it("shows nothing while the file is still uploading or failed", () => {
    expect(slot({ state: "uploading", pagesWithoutText: 2 })).not.toContain("no text");
    expect(slot({ state: "error", code: "PDF_NO_TEXT", pagesWithoutText: 2 })).not.toContain("no text");
  });

  it("is written in Korean too", () => {
    expect(slot(ready(2), "ko")).toContain("2쪽에 텍스트가 없어");
  });
});

describe("drop area accepts one CSV or one PDF", () => {
  it("lists pdf and csv, not images", () => {
    const html = renderToStaticMarkup(
      <NextIntlClientProvider locale="en" messages={en}>
        <FileSlot slot="files" csvOnly items={[]} errors={[]} onAdd={() => undefined} onRemove={() => undefined} />
      </NextIntlClientProvider>,
    );
    expect(html).toContain('accept=".csv,.pdf,text/csv,application/pdf"');
    expect(html).toContain("One CSV or one PDF, up to 5 MB.");
  });
});
