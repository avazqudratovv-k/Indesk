// The closed codes the report API sends (api/app/core/enums.py: ReportReason, EvidenceMethod, Confidence). The browser
// holds the text. A code that is not listed here never reaches the screen: it becomes the neutral "unknown" wording.
export const REASON_CODES = ["rows_mismatch", "bad_reference", "no_numeric_evidence", "label_missing", "number_mismatch", "ranking_unchecked"] as const;
export type ReasonCode = (typeof REASON_CODES)[number];

export const METHOD_CODES = ["rank", "aggregate", "trend", "compare_groups", "count", "describe"] as const;
export type MethodCode = (typeof METHOD_CODES)[number];

export const CONFIDENCE_CODES = ["high", "medium", "low"] as const;
export type ConfidenceCode = (typeof CONFIDENCE_CODES)[number];

const reasonSet: readonly string[] = REASON_CODES;
const methodSet: readonly string[] = METHOD_CODES;
const confidenceSet: readonly string[] = CONFIDENCE_CODES;

// `unknown` is the id of the neutral text under report.reason.unknown and report.method.unknown.
export const reasonId = (code: unknown): ReasonCode | "unknown" => (typeof code === "string" && reasonSet.includes(code) ? (code as ReasonCode) : "unknown");
export const methodId = (code: unknown): MethodCode | "unknown" => (typeof code === "string" && methodSet.includes(code) ? (code as MethodCode) : "unknown");
export const confidenceOf = (code: unknown): ConfidenceCode | null => (typeof code === "string" && confidenceSet.includes(code) ? (code as ConfidenceCode) : null);

// The one tool the report names today. Any other value is left out, never printed.
export const toolLabelId = (tool: unknown): "pandas" | null => (tool === "run_python" ? "pandas" : null);

// "rows 1–4079" is written by the server (Evidence.location of the D1 table). It is parsed, never shown as it came.
export function parseRowsLocation(location: string | null): { from: number; to: number } | null {
  const match = /^rows (\d{1,9})\s*[–-]\s*(\d{1,9})$/.exec(location ?? "");
  return match ? { from: Number(match[1]), to: Number(match[2]) } : null;
}
