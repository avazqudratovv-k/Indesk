// v1 entities. Field names and values follow docs/ai/DATA.md section 1 exactly (snake_case, as the API will send them).
// Timestamps are ISO 8601 strings. Not here on purpose: password_hash and token_hash-style secrets never reach the browser.

export type Plan = "free" | "pro" | "payg" | "custom";
export type Lang = "en" | "ko" | "ja" | "ru" | "uz";

export type User = {
  id: string;
  email: string;
  display_name: string;
  handle: string;
  discoverable: boolean;
  plan: Plan;
  lang: Lang;
  theme: "light" | "dark";
  default_view: "simple" | "detailed";
  notify: boolean;
  created_at: string;
  deleted_at: string | null;
};

// What People search may show about someone else.
export type PersonResult = Pick<User, "id" | "display_name" | "handle">;

export type RefreshToken = {
  id: string;
  user_id: string;
  family_id: string;
  token_hash: string;
  replaced_by: string | null;
  expires_at: string;
  revoked_at: string | null;
};

export type CustomConfig = {
  runs: number;
  max_file_mb: 25 | 100 | 250;
  data_tier: string;
  retention_days: 90 | 180 | 365;
  parallel: 1 | 3 | 5;
};

// Plan prices on the Plans screen are whole Korean won (KRW only, display-only demo values).
export type PlanOffer = {
  plan: "free" | "pro" | "payg";
  runs: number;
  price: number;
  period: "forever" | "month" | "once";
  popular: boolean;
};

// The one set of limits the demo enforces for everyone (api/config/limits.toml). Shown on the Free card and under the cards.
export type DemoLimits = {
  max_file_mb: number;
  csv_rows: number;
  pdf_pages: number;
  runs_per_day: number;
};

export type CustomPlanOffer = {
  runs: { min: number; max: number; step: number; default: number };
  per_run: number;
  minimum: number;
};

export type Subscription = {
  id: string;
  user_id: string;
  plan: "free" | "pro" | "custom";
  status: string;
  custom_config: CustomConfig | null;
  provider_customer_id: string | null;
  current_period_end: string | null;
};

export type Payment = {
  id: string;
  user_id: string;
  provider_ref: string;
  amount: number;
  currency: string;
  status: string;
  test_mode: boolean;
};

export type UsageEvent = {
  id: string;
  user_id: string;
  run_id: string | null;
  kind: "run" | "credit_purchase";
  amount: number;
  created_at: string;
};

export type UploadStatus = "uploaded" | "ready" | "deleted";

export type Upload = {
  id: string;
  user_id: string;
  filename: string;
  mime: string;
  size: number;
  sha256: string;
  storage_key: string | null;
  page_count: number | null;
  row_count: number | null;
  status: UploadStatus;
  moderation: "pending" | "passed" | "blocked";
  created_at: string;
  expires_at: string;
  deleted_at: string | null;
};

export type Chunk = {
  id: string;
  upload_id: string;
  page: number;
  text: string;
  tsv: string | null;
  embedding: string | null;
  ocr_confidence: number | null;
};

export type RunMode = "ask" | "check" | "compare";
export type RunOutcome = "answered" | "partial" | "not_answerable" | "needs_better_input" | "rejected" | "failed";

export type Run = {
  id: string;
  user_id: string;
  question: string;
  mode: RunMode;
  question_type: "new" | "explain" | "reformat" | null;
  status: "queued" | "running" | "finished";
  outcome: RunOutcome | null;
  outcome_reason: string | null;
  counted: boolean;
  lang: Lang;
  tokens_in: number;
  tokens_out: number;
  tool_calls: number;
  cost_usd: number;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
};

export type RunFile = {
  run_id: string;
  upload_id: string;
  role: "subject" | "source" | "a" | "b";
};

export type AgentKey = "manager" | "vision" | "data" | "retrieval" | "critic";

export type StepPayload = {
  claim: string;
  value: string;
  method: string;
  evidence: string[];
  confidence: number;
  caveats: string[];
};

export type AgentStep = {
  id: string;
  run_id: string;
  agent: AgentKey;
  seq: number;
  status: "queued" | "running" | "done" | "skipped" | "failed" | "timed_out";
  attempt: 1 | 2;
  kind: "plan" | "tool" | "result" | "flag";
  payload: StepPayload;
  started_at: string | null;
  finished_at: string | null;
  cost_usd: number;
  model: string | null;
};

// critic_note: why the Critic could not verify a flagged claim (added for the Report screen, ROADMAP 2.7).
export type EvidenceType = "table" | "chart" | "code" | "image_boxes" | "passage" | "diff" | "critic_note";

export type Evidence = {
  id: string;
  run_id: string;
  step_id: string;
  ref: string;
  type: EvidenceType;
  file_name: string;
  location: string | null;
  payload: Record<string, unknown>;
};

// summary_json is free-form jsonb in DATA.md; only `answer` is documented there.
// The other keys are PLACEHOLDER shapes invented for the Check and Compare screens (ROADMAP 2.10, 2.11). Revisit with the API (3.13, 3.14).
export type ReportRowStatus = "verified" | "flagged";

export type ReportSummary = {
  answer: string;
  // Ask (ROADMAP 2.7). Values and statuses come from code; the prose (answer, in_short, meaning, next_steps) from the model.
  top_rows?: { label: string; value: string; status: ReportRowStatus }[];
  in_short?: { status: ReportRowStatus; text: string }[];
  meaning?: string;
  next_steps?: string[];
  not_checked?: string[];
  totals?: { label: string; a: string; b: string; change: string }[];
  movers?: { label: string; change_pct: number }[];
  could_not_compare?: string[];
};

export type ReportMode = "ask" | "check" | "compare";

// Prose of a report in another site language (additive, ROADMAP 2.7b). Numbers, units and station names are the same as in
// the original; top_rows and in_short items pair with the original by position, their value and status stay as they are.
export type ReportTranslation = {
  title: string;
  summary_json: {
    answer?: string;
    top_rows?: { label: string; value: string }[];
    in_short?: { text: string }[];
    meaning?: string;
    next_steps?: string[];
  };
};

export type Report = {
  id: string;
  mode: ReportMode;
  run_id: string;
  owner_id: string;
  title: string;
  summary_json: ReportSummary;
  confidence: "high" | "medium" | "low" | null;
  verified_count: number;
  total_claims: number;
  pdf_key: string | null;
  template: "plain" | "classic" | "compact" | "summary";
  typeface: "clean" | "serif" | "technical";
  text_size: "s" | "m" | "l";
  created_at: string;
  expires_at: string;
  deleted_at: string | null;
  purge_at: string | null;
  translations?: { ko?: ReportTranslation };
};

export type ClaimStatus = "verified" | "flagged" | "unverified" | "mismatch";

export type Claim = {
  id: string;
  report_id: string;
  n: number;
  text: string;
  status: ClaimStatus;
  origin: "answer" | "document";
  doc_quote: string | null;
  doc_location: string | null;
  doc_value: string | null;
  computed_value: string | null;
  evidence_refs: string[];
  // Claim text in Korean; doc_quote stays in the language of the file.
  ko?: { text: string };
};

export type ShareLink = {
  id: string;
  report_id: string;
  token_hash: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
};

export type ShareLinkState = "active" | "expired" | "revoked";

export type AiCall = {
  id: string;
  run_id: string | null;
  step_id: string | null;
  user_id: string;
  purpose: "route" | "plan" | "pick" | "compute" | "vision" | "critic" | "extract_claims" | "embed";
  model: string;
  attempt: 1 | 2 | 3;
  status: "ok" | "rate_limited" | "timeout" | "error";
  tokens_in: number;
  tokens_out: number;
  est_cost_usd: number;
  latency_ms: number;
  created_at: string;
};

export type UsageDaily = {
  day: string;
  user_id: string | null;
  runs: number;
  model_calls: number;
  est_cost_usd: number;
};

export type AuditLog = {
  id: string;
  user_id: string | null;
  action: string;
  target: string | null;
  ip_hash: string | null;
  created_at: string;
};

export type BenchmarkRun = {
  id: string;
  commit_sha: string;
  score: number;
  total: number;
  details: Record<string, unknown>;
};
