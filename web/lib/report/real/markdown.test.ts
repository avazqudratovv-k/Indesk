import { describe, expect, it } from "vitest";
import en from "@/messages/en.json";
import { clone, fixtures } from "./fixtures";
import { buildReportMarkdown, reportFileName } from "./markdown";
import { parseReportDetail } from "./parse";

// A tiny translator over the English "report" messages: {name} placeholders only, enough for these keys.
const say = (key: string, values: Record<string, string | number> = {}): string => {
  const found = key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown> | undefined)?.[part], en.report);
  return String(found).replace(/\{(\w+)(?:, number)?\}/g, (_, name: string) => String(values[name]));
};

const build = (raw: unknown) => buildReportMarkdown(parseReportDetail(raw)!, say);

describe("buildReportMarkdown", () => {
  it("CSV report: title, answer, rows, count line, evidence with file and row range", () => {
    const md = build(fixtures.answered);
    expect(md).toMatch(/^# Gangnam has the most boardings\n/);
    expect(md).toContain("- Gangnam: **412,300** (✓ matches)");
    expect(md).toMatch(/\d of \d claims verified · \w+ confidence/);
    expect(md).toContain("## Evidence");
    expect(md).toContain("- **D1** · seoul_subway_2026-09.csv · Rows 1–4079");
  });

  it("PDF report: page reference and the quoted text, no rows", () => {
    const md = build(fixtures.pdf);
    expect(md).toContain("- **H1** · seoul_subway_2026-09.pdf · p. 4");
    expect(md).toContain("  > Gangnam station recorded 2,450,051 boardings in the month.");
    expect(md).toContain("1 of 1 claims verified · High confidence");
    expect(md).not.toContain("**412");
  });

  it("Korean title and rows stay as written; critic notes are not evidence", () => {
    const md = build(fixtures.korean);
    expect(md).toMatch(/^# 승차 인원이 가장 많은 역\n/);
    expect(md).toContain("잠실(송파구청)");
    expect(md).toContain("! not proven");
    expect(md).not.toContain("U1");
  });

  it("no evidence: no Evidence section", () => {
    const raw = clone(fixtures.answered);
    raw.evidence = [];
    const md = build(raw);
    expect(md).not.toContain("## Evidence");
    expect(md).toContain("# Gangnam has the most boardings");
  });

  it("holds no ids, tokens or links and a hostile quote cannot start a heading", () => {
    const raw = clone(fixtures.pdf);
    raw.evidence[0].payload.quote = "# injected\n- item\u202E";
    const md = build(raw);
    expect(md).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
    expect(md).not.toMatch(/https?:|share|token/i);
    expect(md).toContain("  > # injected - item");
    expect(md).not.toContain("\u202E");
    expect(md.endsWith("\n")).toBe(true);
  });
});

describe("reportFileName", () => {
  const day = new Date(2026, 9, 31);
  it("slugs an English title and adds the date", () => {
    expect(reportFileName("Gangnam has the most boardings!", day)).toBe("gangnam-has-the-most-boardings-2026-10-31.md");
  });
  it("keeps Hangul, drops path characters, falls back to report", () => {
    expect(reportFileName("승차 인원이 가장 많은 역", day)).toBe("승차-인원이-가장-많은-역-2026-10-31.md");
    expect(reportFileName("../../etc/passwd", day)).toBe("etc-passwd-2026-10-31.md");
    expect(reportFileName("???", day)).toBe("report-2026-10-31.md");
  });
  it("caps the length", () => {
    expect(reportFileName("a".repeat(200), day).length).toBe(60 + "-2026-10-31.md".length);
  });
});
