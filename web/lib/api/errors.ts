// The API answers errors as {"error":{"code"}}. Only the code is read; any message text is ignored (never shown).
export const knownCodes = [
  "VALIDATION_ERROR",
  "NOT_FOUND",
  "METHOD_NOT_ALLOWED",
  "NOT_READY",
  "INTERNAL",
  "EMAIL_TAKEN",
  "INVALID_CREDENTIALS",
  "RATE_LIMITED",
  "UNAUTHENTICATED",
  "ORIGIN_NOT_ALLOWED",
  "UNSUPPORTED_TYPE",
  "CONSENT_REQUIRED",
  "FILE_TOO_LARGE",
  "TYPE_MISMATCH",
  "TOO_MANY_ROWS",
  "TOO_MANY_COLUMNS",
  "EMPTY_FILE",
  "BAD_CSV",
  "MODE_NOT_AVAILABLE",
  "DAILY_CAP_USER",
  "DAILY_CAP_GLOBAL",
  "QUOTA_EXHAUSTED",
  "NOT_RETRYABLE",
  "MODEL_UNAVAILABLE",
  "RUN_ACTIVE",
  "UPLOAD_NOT_READY",
  "TOO_MANY_STREAMS",
  "TOO_MANY_FILES",
  "UPLOAD_IN_USE",
  "NETWORK",
  "UNKNOWN",
] as const;

export type ApiErrorCode = (typeof knownCodes)[number];

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  // Seconds from the Retry-After header, when the server sent a usable one.
  readonly retryAfter?: number;
  // Only on RUN_ACTIVE: the run that is in the way (additive field of the error body, DECISIONS #257).
  readonly runId?: string;

  constructor(status: number, code: ApiErrorCode, retryAfter?: number, runId?: string) {
    super(code);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
    this.runId = runId;
  }
}

export function networkError(): ApiError {
  return new ApiError(0, "NETWORK");
}

const runIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const maxRetryAfter = 24 * 60 * 60;

export function parseRetryAfter(value: string | null): number | undefined {
  if (value === null || !/^\d{1,9}$/.test(value.trim())) return undefined;
  const seconds = Number(value);
  return seconds >= 1 ? Math.min(seconds, maxRetryAfter) : undefined;
}

// Fallback for a code we do not know yet (a code added to the API but not to this list yet): by status only.
function codeFromStatus(status: number): ApiErrorCode {
  if (status === 401) return "UNAUTHENTICATED";
  if (status === 403) return "ORIGIN_NOT_ALLOWED";
  if (status === 404) return "NOT_FOUND";
  if (status === 413) return "FILE_TOO_LARGE";
  if (status === 415) return "UNSUPPORTED_TYPE";
  if (status === 422) return "VALIDATION_ERROR";
  if (status === 429) return "RATE_LIMITED";
  if (status === 503) return "NOT_READY";
  if (status >= 500) return "INTERNAL";
  return "UNKNOWN";
}

export async function errorFromResponse(response: Response): Promise<ApiError> {
  const retryAfter = parseRetryAfter(response.headers.get("Retry-After"));
  let code: ApiErrorCode | undefined;
  let runId: string | undefined;
  try {
    const body: unknown = await response.json();
    const error = (body as { error?: { code?: unknown; run_id?: unknown } } | null)?.error;
    const raw = error?.code;
    if (typeof raw === "string" && (knownCodes as readonly string[]).includes(raw)) code = raw as ApiErrorCode;
    // The id is kept only for RUN_ACTIVE and only when it looks like an id; it is used in a request path later.
    if (code === "RUN_ACTIVE" && typeof error?.run_id === "string" && runIdPattern.test(error.run_id)) runId = error.run_id;
  } catch {
    // Not JSON (for example a proxy error page): use the status.
  }
  return new ApiError(response.status, code ?? codeFromStatus(response.status), retryAfter, runId);
}

// Key under `apiErrors` in the message files. A usable Retry-After picks the "wait" wording.
export type ApiErrorKey = ApiErrorCode | "RATE_LIMITED_WAIT";

export function apiErrorKey(error: ApiError): ApiErrorKey {
  if (error.code === "RATE_LIMITED" && error.retryAfter !== undefined) return "RATE_LIMITED_WAIT";
  return error.code;
}

// Whole minutes for the "try again in N minutes" text; never less than 1.
export function retryMinutes(error: ApiError): number {
  return Math.max(1, Math.ceil((error.retryAfter ?? 60) / 60));
}
