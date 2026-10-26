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
  "NETWORK",
  "UNKNOWN",
] as const;

export type ApiErrorCode = (typeof knownCodes)[number];

export class ApiError extends Error {
  readonly status: number;
  readonly code: ApiErrorCode;
  // Seconds from the Retry-After header, when the server sent a usable one.
  readonly retryAfter?: number;

  constructor(status: number, code: ApiErrorCode, retryAfter?: number) {
    super(code);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

export function networkError(): ApiError {
  return new ApiError(0, "NETWORK");
}

const maxRetryAfter = 24 * 60 * 60;

export function parseRetryAfter(value: string | null): number | undefined {
  if (value === null || !/^\d{1,9}$/.test(value.trim())) return undefined;
  const seconds = Number(value);
  return seconds >= 1 ? Math.min(seconds, maxRetryAfter) : undefined;
}

// Fallback for a code we do not know yet (for example an upload code before 4.2 maps it): by status only.
function codeFromStatus(status: number): ApiErrorCode {
  if (status === 401) return "UNAUTHENTICATED";
  if (status === 403) return "ORIGIN_NOT_ALLOWED";
  if (status === 404) return "NOT_FOUND";
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
  try {
    const body: unknown = await response.json();
    const raw = (body as { error?: { code?: unknown } } | null)?.error?.code;
    if (typeof raw === "string" && (knownCodes as readonly string[]).includes(raw)) code = raw as ApiErrorCode;
  } catch {
    // Not JSON (for example a proxy error page): use the status.
  }
  return new ApiError(response.status, code ?? codeFromStatus(response.status), retryAfter);
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
