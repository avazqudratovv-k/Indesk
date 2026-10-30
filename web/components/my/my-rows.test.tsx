import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import type { FileRow, ReportRow } from "@/lib/my/api";
import FileRowItem from "./FileRowItem";
import FilesSection from "./FilesSection";
import ReportRowItem from "./ReportRowItem";
import ReportsSection from "./ReportsSection";
import MyView from "./MyView";

// The page now holds the Log out button, which uses the router.
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));

const id = "11111111-1111-4111-8111-111111111111";
const now = Date.parse("2026-10-31T00:00:00Z");

const report: ReportRow = {
  id,
  title: "Fastest-growing stations",
  createdAt: "2026-10-30T08:00:00Z",
  expiresAt: "2026-11-06T08:00:00Z",
  verified: 5,
  total: 6,
  outcome: "partial",
  fileKind: "csv",
  fileCount: 3,
};

const file: FileRow = { id, name: "seoul.csv", kind: "csv", size: 1_800_000, pages: null, rows: 4200, deleted: false, expiresAt: "2026-10-31T17:00:00Z" };

function render(locale: "en" | "ko", node: React.ReactNode) {
  return renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko} timeZone="UTC" now={new Date(now)}>
      {node}
    </NextIntlClientProvider>,
  );
}

describe("a report row", () => {
  it("shows title, counts, outcome, expiry, an Open link and a Delete button", () => {
    const html = render("en", <ReportRowItem row={report} onDeleted={() => {}} />);
    expect(html).toContain("Fastest-growing stations");
    expect(html).toContain("5 of 6 verified");
    expect(html).toContain("3 files");
    expect(html).toContain("Partly answered");
    expect(html).toContain("Available until Nov 6, 2026");
    expect(html).toContain(`href="/reports/${id}"`);
    expect(html).toContain(">Delete<");
    expect(html).not.toContain("Delete this report?");
  });

  it("reads in Korean", () => {
    const html = render("ko", <ReportRowItem row={report} onDeleted={() => {}} />);
    expect(html).toContain("6개 중 5개 검증");
    expect(html).toContain("파일 3개");
    expect(html).toContain(">열기<");
    expect(html).toContain(">삭제<");
  });

  it("puts the title in a text node, so markup in it is escaped", () => {
    const html = render("en", <ReportRowItem row={{ ...report, title: "<img src=x onerror=alert(1)>" }} onDeleted={() => {}} />);
    expect(html).not.toContain("<img");
  });
});

describe("a file row", () => {
  it("shows kind, name, size, rows and the time left", () => {
    const html = render("en", <FileRowItem row={file} now={now} onDeleted={() => {}} />);
    expect(html).toContain(">CSV<");
    expect(html).toContain("seoul.csv");
    expect(html).toContain("1.72 MB");
    expect(html).toContain("4,200 rows");
    expect(html).toContain("Deleted in 17 h");
    expect(html).toContain(">Delete<");
  });

  it("shows pages for a PDF and the Korean time left", () => {
    const html = render("ko", <FileRowItem row={{ ...file, kind: "pdf", rows: null, pages: 12 }} now={now} onDeleted={() => {}} />);
    expect(html).toContain("12쪽");
    expect(html).toContain("17시간 후 삭제");
  });

  it("shows an already-deleted file as a muted Deleted row with no Delete button", () => {
    const html = render("en", <FileRowItem row={{ ...file, deleted: true }} now={now} onDeleted={() => {}} />);
    expect(html).toContain(">Deleted<");
    expect(html).toContain("fileGone");
    expect(html).not.toContain(">Delete<");
  });

  it("says Deleted soon when the time has passed but the server has not removed it yet", () => {
    const html = render("en", <FileRowItem row={{ ...file, expiresAt: "2026-10-30T00:00:00Z" }} now={now} onDeleted={() => {}} />);
    expect(html).toContain("Deleted soon");
  });
});

describe("the page", () => {
  it("starts in the loading state with its heading and honest copy", () => {
    const html = render("en", <MyView />);
    expect(html).toContain("<h1");
    expect(html).toContain("My page");
    expect(html).toContain("Your reports");
    expect(html).toContain("Files you uploaded");
    expect(html).toContain("Loading…");
    expect(html).toContain("Only you can open your reports.");
    expect(html).toContain("Deleting a report removes its evidence and the saved run. It does not give back a free run.");
    expect(html).toContain("The file and its extracted text are deleted about 24 hours after upload. Reports keep the evidence they quoted.");
    expect(html).toContain("Deletes the file and its extracted text now. Reports that used it keep their evidence.");
    expect(html).toContain("Indesk is a demo. Do not upload private or sensitive files.");
  });

  it("marks each section busy while it loads", () => {
    expect(render("en", <ReportsSection />)).toContain('aria-busy="true"');
    expect(render("en", <FilesSection />)).toContain('aria-busy="true"');
  });
});

describe("the copy", () => {
  it("has the same keys in English and Korean", () => {
    const keys = (value: unknown, prefix = ""): string[] =>
      Object.entries(value as Record<string, unknown>).flatMap(([k, v]) => (typeof v === "object" && v !== null ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`]));
    expect(keys(ko.my).sort()).toEqual(keys(en.my).sort());
  });

  it("makes no promises about sharing, downloads, email or retention days", () => {
    const text = JSON.stringify([en.my, ko.my]).toLowerCase();
    for (const word of ["share", "download", "email", "30 days", "7 days", "공유", "다운로드", "이메일", "30일", "7일"]) expect(text).not.toContain(word);
  });

  it("uses no 은(는) style particle markers in Korean", () => {
    expect(JSON.stringify(ko.my)).not.toMatch(/\((은|는|이|가|을|를)\)|은\(는\)|이\(가\)|을\(를\)/);
  });
});
