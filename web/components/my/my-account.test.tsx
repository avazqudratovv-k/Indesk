import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";
import { SessionContext } from "@/hooks/use-session";
import en from "@/messages/en.json";
import ko from "@/messages/ko.json";
import type { FileRow } from "@/lib/my/api";
import { displayInitial } from "@/lib/my/display";
import { signedInSession } from "@/lib/session";
import type { User } from "@/lib/types";
import FileRowItem from "./FileRowItem";
import MyHeader from "./MyHeader";
import { UsageCardView, type UsageState } from "./UsageCard";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }), usePathname: () => "/my" }));

const now = Date.parse("2026-10-31T00:00:00Z");

function render(locale: "en" | "ko", node: React.ReactNode) {
  return renderToStaticMarkup(
    <NextIntlClientProvider locale={locale} messages={locale === "en" ? en : ko} timeZone="UTC" now={new Date(now)}>
      {node}
    </NextIntlClientProvider>,
  );
}

const user = (over: Partial<User>): User => ({
  id: "u1",
  email: "kim@example.com",
  display_name: "Kim",
  handle: "kim",
  discoverable: false,
  plan: "free",
  lang: "en",
  theme: "light",
  default_view: "simple",
  notify: false,
  created_at: "2026-10-01T00:00:00Z",
  deleted_at: null,
  ...over,
});

function header(locale: "en" | "ko", u: User) {
  return render(
    locale,
    <SessionContext.Provider value={{ session: signedInSession(u), startSession: () => {}, endSession: async () => {} }}>
      <MyHeader />
    </SessionContext.Provider>,
  );
}

const noop = () => {};
const ready = (usage: Extract<UsageState, { status: "ready" }>["usage"]): UsageState => ({ status: "ready", usage });

describe("the header", () => {
  it("shows the initial, the title, the address and the plan name", () => {
    const html = header("en", user({}));
    expect(html).toContain(">K<");
    expect(html).toContain("My page");
    expect(html).toContain("kim@example.com · Free plan");
  });

  it("takes the first Hangul syllable of a Korean name and reads in Korean", () => {
    const html = header("ko", user({ display_name: "김민수" }));
    expect(html).toContain(">김<");
    expect(html).toContain("kim@example.com · 무료 플랜");
  });

  it("takes initials: Latin is upper-cased, Hangul typed as jamo is composed, empty is a question mark", () => {
    expect(displayInitial("  ada")).toBe("A");
    expect(displayInitial("김".normalize("NFD"))).toBe("김");
    expect(displayInitial("   ")).toBe("?");
  });

  it("has no Pro toggle", () => {
    expect(header("en", user({}))).not.toContain("checkbox");
  });
});

describe("the usage card", () => {
  it("shows the counts and a bar for the Free plan, not per month", () => {
    const html = render("en", <UsageCardView state={ready({ plan: "free", free: { total: 3, left: 2 } })} onRetry={noop} />);
    expect(html).toContain("2 of 3 free runs left");
    expect(html).toContain('role="progressbar"');
    expect(html).toContain('aria-valuenow="2"');
    expect(html).toContain('aria-valuemax="3"');
    expect(html).toContain("width:66.6");
    expect(html).not.toContain("month");
    expect(html).not.toContain("No free runs left");
  });

  it("says so when none are left, with an empty bar", () => {
    const html = render("en", <UsageCardView state={ready({ plan: "free", free: { total: 3, left: 0 } })} onRetry={noop} />);
    expect(html).toContain("0 of 3 free runs left");
    expect(html).toContain("width:0%");
    expect(html).toContain("No free runs left. Your reports stay available.");
  });

  it("shows the plan name and no count when the plan has no counts", () => {
    const html = render("en", <UsageCardView state={ready({ plan: "pro", free: null })} onRetry={noop} />);
    expect(html).toContain("Pro plan");
    expect(html).not.toContain("progressbar");
    expect(html).not.toMatch(/\d+ of \d+/);
    expect(render("en", <UsageCardView state={ready({ plan: "mystery", free: null })} onRetry={noop} />)).toContain("Your plan");
  });

  it("reads in Korean", () => {
    const html = render("ko", <UsageCardView state={ready({ plan: "free", free: { total: 3, left: 1 } })} onRetry={noop} />);
    expect(html).toContain("무료 실행 3회 중 1회 남음");
  });

  it("has loading and error states, and neither shows a number", () => {
    const loading = render("en", <UsageCardView state={{ status: "loading" }} onRetry={noop} />);
    expect(loading).toContain("Loading…");
    expect(loading).toContain('aria-busy="true"');
    const error = render("en", <UsageCardView state={{ status: "error" }} onRetry={noop} />);
    expect(error).toContain('role="alert"');
    expect(error).toContain("Could not load this list.");
    expect(error).toContain("Try again");
    expect(error).not.toContain("progressbar");
  });
});

// Same idea as limits.test.ts: api/config/limits.toml is the source, and the line the page prints must carry its numbers.
function readServerLimits(): Record<string, number> {
  const text = readFileSync(resolve(import.meta.dirname, "../../../api/config/limits.toml"), "utf8");
  const values: Record<string, number> = {};
  for (const line of text.split("\n")) {
    if (line.startsWith("[")) break;
    const match = /^([a-z_]+)\s*=\s*(\d+)\s*(#.*)?$/.exec(line);
    if (match) values[match[1]] = Number(match[2]);
  }
  return values;
}

describe("the limits line on the usage card", () => {
  const server = readServerLimits();
  const mb = server.max_file_bytes / (1024 * 1024);
  const rows = server.max_rows.toLocaleString("en-US");

  it("prints the numbers of limits.toml in English", () => {
    const html = render("en", <UsageCardView state={{ status: "loading" }} onRetry={noop} />);
    expect(html).toContain(`${mb} MB per file, ${rows} CSV rows, ${server.max_pdf_pages} PDF pages, ${server.daily_runs_per_user} runs a day.`);
  });

  it("prints the same numbers in Korean", () => {
    const html = render("ko", <UsageCardView state={{ status: "loading" }} onRetry={noop} />);
    expect(html).toContain(`파일당 ${mb}MB, CSV ${rows}행, PDF ${server.max_pdf_pages}쪽, 하루 ${server.daily_runs_per_user}회 실행.`);
  });

  it.each([
    ["en", en],
    ["ko", ko],
  ] as const)("%s: the line takes its numbers as ICU arguments, none written in", (_lang, m) => {
    for (const p of ["{mb, number}", "{rows, number}", "{pages, number}", "{runs, number}"]) expect(m.my.usage.limits).toContain(p);
    expect(m.my.usage.limits).not.toMatch(/\d/);
  });
});

describe("file sizes on My page rows", () => {
  const file: FileRow = { id: "f1", name: "a.csv", kind: "csv", size: 264_909, pages: null, rows: null, deleted: false, expiresAt: "2026-10-31T17:00:00Z" };

  it("uses the workspace formatter: 264,909 bytes is 258.7 KB, never 265 KB", () => {
    const html = render("en", <FileRowItem row={file} now={now} onDeleted={noop} />);
    expect(html).toContain("258.7 KB");
    expect(html).not.toContain("265 KB");
  });

  it("uses MB and B the same way", () => {
    expect(render("en", <FileRowItem row={{ ...file, size: 5 * 1024 * 1024 }} now={now} onDeleted={noop} />)).toContain("5 MB");
    expect(render("en", <FileRowItem row={{ ...file, size: 900 }} now={now} onDeleted={noop} />)).toContain("900 B");
  });
});

describe("the account copy", () => {
  it("has the retention line in both languages and no Delete account, settings toggle or Pro switch", () => {
    expect(en.my.account.retention).toBe("The file and its extracted text are deleted about 24 hours after upload.");
    expect(ko.my.account.retention).toContain("24시간");
    const text = JSON.stringify([en.my, ko.my]).toLowerCase();
    for (const word of ["delete account", "계정 삭제", "open reports in", "preview a pro"]) expect(text).not.toContain(word);
  });

  it("has the nav link name in both languages", () => {
    expect(en.nav.accountLink).toContain("{name}");
    expect(ko.nav.accountLink).toContain("{name}");
    expect(Object.keys(ko.nav).sort()).toEqual(Object.keys(en.nav).sort());
  });
});
