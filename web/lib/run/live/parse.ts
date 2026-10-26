import { BACKEND_AGENTS, BUBBLES, OUTCOMES, STEP_KINDS, STEP_STATES, type LiveDone, type LiveStep, type RunSnapshot, type TraceArgs, type UploadedFile } from "./types";

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

export function parseDone(value: unknown): LiveDone | null {
  if (!isRecord(value)) return null;
  const outcome = oneOf(OUTCOMES, value.outcome);
  if (!outcome) return null;
  return { outcome, reason: typeof value.reason === "string" ? value.reason : null, reportId: typeof value.report_id === "string" ? value.report_id : null };
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
  return {
    id: value.id,
    status,
    outcome: oneOf(OUTCOMES, value.outcome),
    reason: typeof value.reason === "string" ? value.reason : null,
    reportId: typeof value.report_id === "string" ? value.report_id : null,
    question: typeof value.question === "string" ? value.question : "",
    createdAt: time(value.created_at),
    startedAt: time(value.started_at),
    finishedAt: time(value.finished_at),
    steps,
  };
}

export function parseUpload(value: unknown): UploadedFile | null {
  if (!isRecord(value) || typeof value.id !== "string") return null;
  const expiresAt = time(value.expires_at);
  if (expiresAt === null) return null;
  return { id: value.id, expiresAt, rowCount: typeof value.row_count === "number" ? value.row_count : null };
}

export function parseCreated(value: unknown): { id: string } | null {
  return isRecord(value) && isRunId(value.id) ? { id: value.id } : null;
}
