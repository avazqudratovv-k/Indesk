// Shapes of what the run API and the event stream send. Everything is checked in parse.ts before it is used:
// the browser trusts neither field names nor values, and no free text from the server is ever kept.

export const BACKEND_AGENTS = ["manager", "vision", "data", "retrieval", "critic"] as const;
export type BackendAgent = (typeof BACKEND_AGENTS)[number];

export const STEP_KINDS = ["say", "tool", "flag"] as const;
export type StepKind = (typeof STEP_KINDS)[number];

export const STEP_STATES = ["queued", "running", "done", "skipped", "failed", "timed_out"] as const;
export type BackendStepState = (typeof STEP_STATES)[number];

export const BUBBLES = ["owlSplit", "owlMerge"] as const;
export type Bubble = (typeof BUBBLES)[number];

export const OUTCOMES = ["answered", "partial", "not_answerable", "needs_better_input", "rejected", "failed"] as const;
export type Outcome = (typeof OUTCOMES)[number];

export type TraceArgs = Readonly<Record<string, string | number | boolean | null>>;

export type LiveStep = {
  seq: number;
  agent: BackendAgent;
  kind: StepKind;
  state: BackendStepState;
  key: string;
  args: TraceArgs;
  tok: number;
  bubble: Bubble | null;
};

export const NA_REASONS = ["pdf_no_match", "pdf_not_in_passages", "pdf_page_range", "csv_period", "csv_no_rows", "csv_missing_column"] as const;
export type NaReason = (typeof NA_REASONS)[number];

export const NA_KINDS = ["csv_rank", "csv_trend", "pdf_about", "pdf_page"] as const;
export type NaKind = (typeof NA_KINDS)[number];

// Why a run is not answerable (api/app/schemas/not_answerable.py), after parse.ts has checked every field. Every fact is
// optional and absent when the server left it out; text is plain text with a length cap.
export type NaFacts = {
  pageCount?: number;
  pagesWithText?: number;
  searchedPages?: number[];
  askedPage?: number;
  rowCount?: number;
  columns?: string[];
  timeColumn?: string;
  yearMin?: number;
  yearMax?: number;
  askedYear?: number;
  askedColumn?: string;
};
export type NaSuggestion = { text: string; kind: NaKind };
export type NotAnswerable = { reason: NaReason; facts: NaFacts; suggestions: NaSuggestion[] };

// The closing facts of a run. `reason` is kept as the raw code string; reasons.ts decides what it means.
// `notAnswerable` is set only for a not_answerable run whose object passed the strict check.
export type LiveDone = { outcome: Outcome; reason: string | null; reportId: string | null; notAnswerable?: NotAnswerable };

export type RunStatus = "queued" | "running" | "finished";

// GET /api/runs/{id}, reduced to what the screen uses (no question text is kept beyond the title).
export type RunSnapshot = {
  id: string;
  status: RunStatus;
  outcome: Outcome | null;
  reason: string | null;
  reportId: string | null;
  notAnswerable?: NotAnswerable;
  question: string;
  createdAt: number | null;
  startedAt: number | null;
  finishedAt: number | null;
  steps: LiveStep[];
};

// pagesWithoutText: only for a PDF, only when the server sent it; absent for a CSV.
export type UploadedFile = { id: string; expiresAt: number; rowCount: number | null; pagesWithoutText?: number };
