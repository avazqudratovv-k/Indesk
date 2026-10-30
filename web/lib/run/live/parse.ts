import { plainText } from "@/lib/report/real/text";
import { BACKEND_AGENTS, BUBBLES, NA_KINDS, NA_REASONS, OUTCOMES, STEP_KINDS, STEP_STATES, type LiveDone, type LiveStep, type NaFacts, type NaSuggestion, type NotAnswerable, type RunSnapshot, type TraceArgs, type UploadedFile } from "./types";

const keyPattern = /^[A-Za-z][A-Za-z0-9_]{0,63}$/;
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isRunId(value: unknown): value is string {
  return typeof value === "string" && uuidPattern.test(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function oneOf<T extends string>(list: readonly T[], value: unknown): T | null {
  return typeof value === "string" && (list as readonly string[]).includes(value) ? (value as T) : null;
}

function parseArgs(value: unknown): TraceArgs {
  const out: Record<string, string | number | boolean | null> = {};
  if (!isRecord(value)) return out;
  for (const [name, arg] of Object.entries(value)) {
    if (!keyPattern.test(name)) continue;
    if (typeof arg === "string" || typeof arg === "boolean" || arg === null || (typeof arg === "number" && Number.isFinite(arg))) out[name] = arg;
  }
  return out;
}

// A step from the stream or from GET /api/runs/{id}. Anything that does not fit is dropped (null), never rendered.
export function parseStep(value: unknown): LiveStep | null {
  if (!isRecord(value)) return null;
  const agent = oneOf(BACKEND_AGENTS, value.agent);
  const kind = oneOf(STEP_KINDS, value.kind);
  const state = oneOf(STEP_STATES, value.state);
  const { seq, key, tok } = value;
  if (!agent || !kind || !state) return null;
  if (typeof seq !== "number" || !Number.isInteger(seq) || seq < 0) return null;
  if (typeof key !== "string" || !keyPattern.test(key)) return null;
  const bubble = value.bubble === null || value.bubble === undefined ? null : oneOf(BUBBLES, value.bubble);
  return { seq, agent, kind, state, key, args: parseArgs(value.args), tok: typeof tok === "number" && Number.isFinite(tok) && tok >= 0 ? tok : 0, bubble };
}

// Caps mirror api/app/schemas/not_answerable.py (8 pages, 8 columns, 2 suggestions, 200 characters a suggestion).
const NA_MAX_PAGES = 8;
const NA_MAX_COLUMNS = 8;
const NA_MAX_SUGGESTIONS = 2;
const NA_MAX_SUGGESTION_CHARS = 200;
const NA_MAX_NAME_CHARS = 80;
const NA_MAX_NUMBER = 10_000_000;

// A fact that is absent (or null) is left out; a present fact of the wrong type, range or length makes the whole object invalid.
function naInt(value: unknown, min: number): number | null | undefined {
  if (value === undefined || value === null) return undefined;
  return typeof value === "number" && Number.isSafeInteger(value) && value >= min && value <= NA_MAX_NUMBER ? value : null;
}

function naText(value: unknown, max: number): string | null | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "string" || value.length > max) return null;
  const clean = plainText(value, max);
  return clean === "" ? null : clean;
}

function parseNaFacts(value: unknown): NaFacts | null {
  if (!isRecord(value)) return null;
  const facts: NaFacts = {};
  const ints: [keyof NaFacts, string, number][] = [
    ["pageCount", "page_count", 0],
    ["pagesWithText", "pages_with_text", 0],
    ["askedPage", "asked_page", 0],
    ["rowCount", "row_count", 0],
    ["yearMin", "year_min", 0],
    ["yearMax", "year_max", 0],
    ["askedYear", "asked_year", 0],
  ];
  for (const [name, field, min] of ints) {
    const n = naInt(value[field], min);
    if (n === null) return null;
    if (n !== undefined) (facts as Record<string, number>)[name] = n;
  }
  const timeColumn = naText(value.time_column, NA_MAX_NAME_CHARS);
  if (timeColumn === null) return null;
  if (timeColumn !== undefined) facts.timeColumn = timeColumn;
  for (const [name, field, max, cap] of [
    ["searchedPages", "searched_pages", NA_MAX_PAGES, 1],
    ["columns", "columns", NA_MAX_COLUMNS, 0],
  ] as const) {
    const list = value[field];
    if (list === undefined || list === null) continue;
    if (!Array.isArray(list) || list.length > max) return null;
    const items = list.map((item) => (name === "columns" ? naText(item, NA_MAX_NAME_CHARS) : naInt(item, cap)));
    if (items.some((item) => item === null || item === undefined)) return null;
    if (items.length > 0) (facts as Record<string, unknown>)[name] = items;
  }
  return facts;
}

function parseNaSuggestion(value: unknown): NaSuggestion | null {
  if (!isRecord(value)) return null;
  const kind = oneOf(NA_KINDS, value.kind);
  const text = naText(value.text, NA_MAX_SUGGESTION_CHARS);
  return kind && text ? { text, kind } : null;
}

// The `not_answerable` object of a run (run view and done event). Strict: an unknown reason or kind, a wrong type, too
// many items or a too long string makes the whole object null, and the screen falls back to the generic card.
export function parseNotAnswerable(value: unknown): NotAnswerable | null {
  if (!isRecord(value)) return null;
  const reason = oneOf(NA_REASONS, value.reason);
  const facts = parseNaFacts(value.facts);
  const list = value.suggestions === undefined || value.suggestions === null ? [] : value.suggestions;
  if (!reason || !facts || !Array.isArray(list) || list.length > NA_MAX_SUGGESTIONS) return null;
  const suggestions = list.map(parseNaSuggestion);
  if (suggestions.some((item) => item === null)) return null;
  return { reason, facts, suggestions: suggestions as NaSuggestion[] };
}

export function parseDone(value: unknown): LiveDone | null {
  if (!isRecord(value)) return null;
  const outcome = oneOf(OUTCOMES, value.outcome);
  if (!outcome) return null;
  const done: LiveDone = { outcome, reason: typeof value.reason === "string" ? value.reason : null, reportId: typeof value.report_id === "string" ? value.report_id : null };
  const notAnswerable = outcome === "not_answerable" ? parseNotAnswerable(value.not_answerable) : null;
  if (notAnswerable) done.notAnswerable = notAnswerable;
  return done;
}

function time(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

export function parseRunSnapshot(value: unknown): RunSnapshot | null {
  if (!isRecord(value) || !isRunId(value.id)) return null;
  const status = oneOf(["queued", "running", "finished"] as const, value.status);
  if (!status) return null;
  const steps = Array.isArray(value.steps) ? value.steps.map(parseStep).filter((step): step is LiveStep => step !== null) : [];
  const outcome = oneOf(OUTCOMES, value.outcome);
  const snapshot: RunSnapshot = {
    id: value.id,
    status,
    outcome,
    reason: typeof value.reason === "string" ? value.reason : null,
    reportId: typeof value.report_id === "string" ? value.report_id : null,
    question: typeof value.question === "string" ? value.question : "",
    createdAt: time(value.created_at),
    startedAt: time(value.started_at),
    finishedAt: time(value.finished_at),
    steps,
  };
  const notAnswerable = outcome === "not_answerable" ? parseNotAnswerable(value.not_answerable) : null;
  if (notAnswerable) snapshot.notAnswerable = notAnswerable;
  return snapshot;
}

export function parseUpload(value: unknown): UploadedFile | null {
  if (!isRecord(value) || typeof value.id !== "string") return null;
  const expiresAt = time(value.expires_at);
  if (expiresAt === null) return null;
  const upload: UploadedFile = { id: value.id, expiresAt, rowCount: typeof value.row_count === "number" ? value.row_count : null };
  const blank = value.pages_without_text;
  if (typeof blank === "number" && Number.isSafeInteger(blank) && blank >= 0) upload.pagesWithoutText = blank;
  return upload;
}

export function parseCreated(value: unknown): { id: string } | null {
  return isRecord(value) && isRunId(value.id) ? { id: value.id } : null;
}
