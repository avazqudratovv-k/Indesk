// Pure helpers for the Report screen (ROADMAP 2.7). Numbers shown here come from the report data; nothing is calculated by a model.
import type { Claim, ClaimStatus, Evidence, EvidenceType } from "@/lib/types";

export type EvidenceTable = { headers: string[]; rows: string[][] };

export type EvidenceView = {
  ref: string;
  type: EvidenceType;
  title: string;
  body: string;
  tool: string | null;
  code: string | null;
  table: EvidenceTable | null;
  quote: string | null;
  fileName: string;
  location: string | null;
};

export type ChartBar = { label: string; value: number; photo: number | null };
export type ChartView = { title: string; bars: ChartBar[]; max: number };

const asText = (value: unknown): string | null => (typeof value === "string" && value !== "" ? value : null);

function asTable(value: unknown): EvidenceTable | null {
  if (typeof value !== "object" || value === null) return null;
  const { headers, rows } = value as { headers?: unknown; rows?: unknown };
  if (!Array.isArray(headers) || !Array.isArray(rows)) return null;
  return { headers: headers.map(String), rows: rows.map((row) => (Array.isArray(row) ? row.map(String) : [])) };
}

// Payload keys are listed in the _note of web/mocks/evidence.json. Missing keys simply leave a part of the panel out.
export function toEvidenceView(item: Evidence): EvidenceView {
  const p = item.payload;
  return {
    ref: item.ref,
    type: item.type,
    title: asText(p.title) ?? item.file_name,
    body: asText(p.body) ?? "",
    tool: asText(p.tool),
    code: asText(p.code),
    table: asTable(p.table),
    quote: asText(p.quote),
    fileName: item.file_name,
    location: item.location,
  };
}

// The growth chart rides on the payload of the table evidence that carries a `chart` series (D1).
export function toChartView(evidence: Evidence[]): ChartView | null {
  for (const item of evidence) {
    const chart = item.payload.chart;
    if (typeof chart !== "object" || chart === null) continue;
    const { title, series } = chart as { title?: unknown; series?: unknown };
    if (!Array.isArray(series)) continue;
    const bars: ChartBar[] = series.flatMap((entry) => {
      const { label, value, photo_value } = entry as { label?: unknown; value?: unknown; photo_value?: unknown };
      return typeof label === "string" && typeof value === "number" ? [{ label, value, photo: typeof photo_value === "number" ? photo_value : null }] : [];
    });
    if (bars.length === 0) continue;
    return { title: asText(title) ?? "", bars, max: axisMax(bars) };
  }
  return null;
}

// Axis end: the largest value (data or photo) rounded up to the next multiple of 5, so 18.2 gives 20 as on the board.
export function axisMax(bars: ChartBar[]): number {
  const top = Math.max(...bars.flatMap((bar) => (bar.photo === null ? [bar.value] : [bar.value, bar.photo])));
  return Math.max(5, Math.ceil(top / 5) * 5);
}

export const percent = (value: number): string => `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(1)}%`;
export const photoPercent = (value: number): string => `${value >= 0 ? "+" : "−"}${Math.abs(value)}%`;
export const barWidth = (value: number, max: number): string => `${Math.min(100, Math.max(0, (value / max) * 100))}%`;

export const padNumber = (n: number): string => String(n).padStart(2, "0");

// A claim counts as proven only when its status is "verified" (AGENTS.md: a claim without evidence is never shown as verified).
export const isProven = (status: ClaimStatus): boolean => status === "verified";

export function visibleClaims(claims: Claim[], showUnverified: boolean): Claim[] {
  return [...claims].sort((a, b) => a.n - b.n).filter((claim) => showUnverified || isProven(claim.status));
}

// First evidence of the first claim that has any, else the first record; null when the run left none.
export function defaultEvidenceRef(claims: Claim[], evidence: Evidence[]): string | null {
  const ordered = [...claims].sort((a, b) => a.n - b.n);
  for (const claim of ordered) {
    const ref = claim.evidence_refs.find((candidate) => evidence.some((item) => item.ref === candidate));
    if (ref) return ref;
  }
  return evidence[0]?.ref ?? null;
}

// "page 12" becomes "p.12"; anything else is returned as is.
export function shortLocation(location: string | null): string | null {
  if (!location) return null;
  const match = /^page (\d+)$/.exec(location);
  return match ? `p.${match[1]}` : location;
}

export const CONFIDENCE_LEVELS = ["high", "medium", "low"] as const;
