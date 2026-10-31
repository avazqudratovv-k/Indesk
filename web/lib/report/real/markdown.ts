import type { ReportBundle } from "../get-report";
import { pageOf, parseRowsLocation } from "./codes";
import type { Say } from "./evidence-view";
import { plainText } from "./text";

// The .md download of a real report: built in the browser from the bundle the page already loaded, so it holds exactly what
// the owner sees (title, answer, verified rows, count and confidence line, evidence) and nothing else. No ids, no tokens,
// no user data, no share links. Everything from the server goes through plainText (controls and direction marks dropped).
// `say` is the translator of the "report" namespace.
const LONG = 2000;

// One line of text: a table cell or label cannot carry a line break into the markdown.
const line = (value: unknown, max = 400): string => plainText(value, max);

// A quote keeps its own lines but every line is a blockquote line, so it can never start a heading or a list.
function quoteBlock(text: string): string {
  return text
    .split(/\r?\n/)
    .map((part) => plainText(part, LONG))
    .filter(Boolean)
    .map((part) => `  > ${part}`)
    .join("\n");
}

function evidenceLines(bundle: ReportBundle, say: Say): string[] {
  const out: string[] = [];
  for (const item of bundle.evidence) {
    // A critic note is the reason a claim is not verified, not evidence for it.
    if (item.type === "critic_note") continue;
    const page = typeof item.payload.page === "number" ? item.payload.page : pageOf(item.location);
    const range = parseRowsLocation(item.location);
    const parts = [line(item.file_name, 200), page !== null ? say("evidence.page", { n: page }) : "", range ? say("evidence.rows", { from: range.from, to: range.to }) : ""].filter(Boolean);
    const quote = [item.payload.quote, item.payload.passage].find((text): text is string => typeof text === "string" && text !== "");
    out.push(`- **${line(item.ref, 20)}**${parts.length > 0 ? ` · ${parts.join(" · ")}` : ""}`);
    if (quote) out.push(quoteBlock(quote));
  }
  return out;
}

export function buildReportMarkdown(bundle: ReportBundle, say: Say): string {
  const { report } = bundle;
  const summary = report.summary_json;
  const parts: string[] = [`# ${line(report.title, 300)}`];
  const answer = plainText(summary.answer, LONG);
  if (answer) parts.push(answer);
  const rows = (summary.top_rows ?? []).map((row) => `- ${line(row.label, 200)}: **${line(row.value, 200)}** (${say(row.status === "verified" ? "paper.rowMatches" : "paper.rowNotProven")})`);
  if (rows.length > 0) parts.push(rows.join("\n"));
  if (report.total_claims > 0) {
    const level = report.confidence ? ` · ${say(`confidence.${report.confidence}`)}` : "";
    parts.push(`${say("download.md.count", { verified: report.verified_count, total: report.total_claims })}${level}`);
  }
  const evidence = evidenceLines(bundle, say);
  if (evidence.length > 0) parts.push(`## ${say("download.md.evidence")}\n\n${evidence.join("\n")}`);
  return `${parts.join("\n\n")}\n`;
}

// A safe file name: letters and digits of any script (Hangul stays), everything else becomes one hyphen, at most 60
// characters, plus the date. No path characters can survive. An empty slug becomes "report".
export function reportFileName(title: string, date: Date): string {
  const slug = title
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60)
    .replace(/-+$/g, "");
  const day = [date.getFullYear(), date.getMonth() + 1, date.getDate()].map((n, index) => String(n).padStart(index === 0 ? 4 : 2, "0")).join("-");
  return `${slug || "report"}-${day}.md`;
}
