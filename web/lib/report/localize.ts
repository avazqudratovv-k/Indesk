// Picks the prose of a report for the site language (ROADMAP 2.7b). Any field the translation leaves out keeps the original text.
import { defaultLocale, type Locale } from "@/i18n/config";
import type { Claim, Evidence, Report, ReportSummary } from "@/lib/types";

type Chart = { title?: unknown; series?: unknown };
type EvidenceKo = { title?: string; body?: string; table?: unknown; chart?: { title?: string; series?: { label?: string }[] } };

// Pairs translated items with the originals by position.
function byIndex<T, U>(items: T[] | undefined, texts: U[] | undefined, merge: (item: T, text: U) => T): T[] | undefined {
  return items?.map((item, i) => (texts?.[i] === undefined ? item : merge(item, texts[i])));
}

export function localizeReport(report: Report, locale: Locale): Report {
  const ko = locale === "ko" ? report.translations?.ko : undefined;
  if (!ko) return report;
  const t = ko.summary_json;
  const summary: ReportSummary = {
    ...report.summary_json,
    answer: t.answer ?? report.summary_json.answer,
    top_rows: byIndex(report.summary_json.top_rows, t.top_rows, (row, text) => ({ ...row, label: text.label ?? row.label, value: text.value ?? row.value })),
    in_short: byIndex(report.summary_json.in_short, t.in_short, (item, text) => ({ ...item, text: text.text ?? item.text })),
    meaning: t.meaning ?? report.summary_json.meaning,
    next_steps: report.summary_json.next_steps?.map((step, i) => t.next_steps?.[i] ?? step),
  };
  return { ...report, title: ko.title || report.title, summary_json: summary };
}

export function localizeClaim(claim: Claim, locale: Locale): Claim {
  return locale === "ko" && claim.ko ? { ...claim, text: claim.ko.text || claim.text } : claim;
}

export function localizeEvidence(item: Evidence, locale: Locale): Evidence {
  const { ko, ...payload } = item.payload as Record<string, unknown> & { ko?: EvidenceKo };
  if (locale !== defaultLocale && ko) {
    if (ko.title) payload.title = ko.title;
    if (ko.body) payload.body = ko.body;
    if (ko.table) payload.table = ko.table;
    const chart = payload.chart as Chart | undefined;
    if (ko.chart && chart && Array.isArray(chart.series)) {
      const series = chart.series as { label: string }[];
      payload.chart = {
        ...chart,
        title: ko.chart.title ?? chart.title,
        series: series.map((bar, i) => ({ ...bar, label: ko.chart?.series?.[i]?.label ?? bar.label })),
      };
    }
  }
  return { ...item, payload };
}
