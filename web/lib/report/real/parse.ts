import type { Claim, ClaimStatus, Evidence, EvidenceType, Report, ReportSummary } from "@/lib/types";
import type { ReportBundle } from "../get-report";
import { confidenceOf } from "./codes";
import { plainText } from "./text";

// GET /api/reports/{id}, checked field by field. The browser trusts neither names nor values: a body of the wrong shape
// gives null (the screen shows its error state), a value outside a closed list is mapped to a safe one, and every text
// goes through plainText().
const CLAIM_STATUSES: readonly ClaimStatus[] = ["verified", "flagged", "unverified", "mismatch"];
const EVIDENCE_TYPES: readonly EvidenceType[] = ["table", "chart", "code", "image_boxes", "passage", "diff", "critic_note"];

const MAX_CLAIMS = 100;
const MAX_EVIDENCE = 120;
const MAX_ROWS = 100;
const MAX_COLUMNS = 40;

type Obj = Record<string, unknown>;
const isObj = (value: unknown): value is Obj => typeof value === "object" && value !== null && !Array.isArray(value);
const count = (value: unknown): number | null => (typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 1_000_000 ? value : null);
const str = (value: unknown): string | null => (typeof value === "string" ? value : null);

function parseRef(value: unknown): string | null {
  return typeof value === "string" && /^[A-Za-z][A-Za-z0-9]{0,11}$/.test(value) ? value : null;
}

// A row of an evidence table is a list of cells (strings). Anything else makes the table unusable, so it is dropped.
function parseTable(value: unknown): { headers: string[]; rows: string[][] } | null {
  if (!isObj(value) || !Array.isArray(value.headers) || !Array.isArray(value.rows)) return null;
  if (value.headers.length > MAX_COLUMNS || value.rows.length > MAX_ROWS) return null;
  const headers = value.headers.map((header) => plainText(header, 120));
  const rows = value.rows.map((row) => (Array.isArray(row) ? row.slice(0, MAX_COLUMNS).map((cell) => plainText(typeof cell === "number" ? String(cell) : cell, 200)) : []));
  return { headers, rows };
}

function parseSummary(value: unknown): ReportSummary | null {
  if (!isObj(value)) return null;
  const answer = plainText(value.answer, 2000);
  if (!answer) return null;
  const rowStatus = (status: unknown) => (status === "verified" ? ("verified" as const) : ("flagged" as const));
  const list = (items: unknown, max: number) => (Array.isArray(items) ? items.slice(0, max) : undefined);
  const topRows = list(value.top_rows, 10)?.flatMap((row) => (isObj(row) ? [{ label: plainText(row.label, 200), value: plainText(row.value, 120), status: rowStatus(row.status) }] : []));
  const inShort = list(value.in_short, MAX_CLAIMS)?.flatMap((item) => (isObj(item) ? [{ status: rowStatus(item.status), text: plainText(item.text, 600) }] : []));
  const nextSteps = list(value.next_steps, 10)?.map((step) => plainText(step, 400)).filter(Boolean);
  const meaning = plainText(value.meaning, 2000);
  return { answer, top_rows: topRows, in_short: inShort, meaning: meaning || undefined, next_steps: nextSteps };
}

function parseClaim(value: unknown, reportId: string): Claim | null {
  if (!isObj(value)) return null;
  const id = str(value.id);
  const n = count(value.n);
  const text = plainText(value.text, 600);
  if (!id || n === null || !text || !Array.isArray(value.evidence_refs)) return null;
  const status = CLAIM_STATUSES.find((candidate) => candidate === value.status) ?? "unverified";
  const refs = value.evidence_refs.flatMap((ref) => {
    const clean = parseRef(ref);
    return clean ? [clean] : [];
  });
  return {
    id, report_id: reportId, n, text, status, origin: "answer", doc_quote: null, doc_location: null, doc_value: null,
    computed_value: typeof value.computed_value === "string" ? plainText(value.computed_value, 120) : null,
    evidence_refs: refs,
  };
}

function parseEvidence(value: unknown, runId: string): Evidence | null {
  if (!isObj(value) || !isObj(value.payload)) return null;
  const id = str(value.id);
  const ref = parseRef(value.ref);
  const type = EVIDENCE_TYPES.find((candidate) => candidate === value.type);
  if (!id || !ref || !type) return null;
  const payload = value.payload;
  // Only the keys the real screen uses are kept. `code` is never kept: v1 shows no code (DECISIONS #225).
  const kept: Record<string, unknown> = {
    tool: str(payload.tool) ?? undefined,
    rows_used: count(payload.rows_used) ?? undefined,
    reason: str(payload.reason) ?? undefined,
    method: str(payload.method) ?? undefined,
    table: parseTable(payload.table) ?? undefined,
  };
  return { id, run_id: runId, step_id: str(value.step_id) ?? "", ref, type, file_name: plainText(value.file_name, 200), location: typeof value.location === "string" ? plainText(value.location, 60) : null, payload: kept };
}

export function parseReportDetail(raw: unknown): ReportBundle | null {
  if (!isObj(raw) || !isObj(raw.report) || !Array.isArray(raw.claims) || !Array.isArray(raw.evidence)) return null;
  const r = raw.report;
  const id = str(r.id);
  const runId = str(r.run_id);
  const summary = parseSummary(r.summary_json);
  const verified = count(r.verified_count);
  const total = count(r.total_claims);
  if (!id || !runId || !summary || verified === null || total === null || verified > total) return null;
  if (raw.claims.length > MAX_CLAIMS || raw.evidence.length > MAX_EVIDENCE) return null;
  const claims = raw.claims.map((claim) => parseClaim(claim, id));
  const evidence = raw.evidence.map((item) => parseEvidence(item, runId));
  if (claims.includes(null) || evidence.includes(null)) return null;
  const mode = r.mode === "check" || r.mode === "compare" ? r.mode : "ask";
  const report: Report = {
    id, mode, run_id: runId, owner_id: str(r.owner_id) ?? "", title: plainText(r.title, 300) || summary.answer.slice(0, 120),
    summary_json: summary, confidence: confidenceOf(r.confidence), verified_count: verified, total_claims: total, pdf_key: null,
    template: "plain", typeface: "clean", text_size: "m", created_at: str(r.created_at) ?? "", expires_at: str(r.expires_at) ?? "", deleted_at: null, purge_at: null,
  };
  return { report, claims: claims as Claim[], evidence: evidence as Evidence[] };
}
