import { apiClient } from "@/lib/api/client";
import { ApiError, type ApiErrorCode } from "@/lib/api/errors";
import { isRealReportId } from "@/lib/report/real/id";
import { plainText } from "@/lib/report/real/text";

// My page data: the owner's reports and uploads. Rows come from the server and are parsed strictly: a row that does not
// have the expected shape is dropped, never repaired, and extra fields are ignored. All text goes through plainText.
export type ReportRow = {
  id: string;
  title: string;
  createdAt: string;
  expiresAt: string;
  verified: number;
  total: number;
  outcome: "answered" | "partial";
  fileKind: "csv" | "pdf" | null;
  fileCount: number;
};

export type ReportsPage = { items: ReportRow[]; nextCursor: string | null };

export type FileRow = {
  id: string;
  name: string;
  kind: "csv" | "pdf" | "jpg" | "png" | "txt";
  size: number;
  pages: number | null;
  rows: number | null;
  deleted: boolean;
  expiresAt: string;
};

type Request = <T>(path: string, init?: { signal?: AbortSignal; method?: "GET" | "DELETE" }) => Promise<T>;
const defaultRequest: Request = <T,>(path: string, init?: { signal?: AbortSignal; method?: "GET" | "DELETE" }) => apiClient().request<T>(path, init);

const maxTitle = 200;
const maxName = 255;
const maxCursor = 512;
export const pageSize = 20;

const whole = (value: unknown): value is number => typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value <= 1_000_000_000;
const object = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);
const instant = (value: unknown): value is string => typeof value === "string" && value.length <= 40 && !Number.isNaN(Date.parse(value));

export function parseReportRow(raw: unknown): ReportRow | null {
  if (!object(raw)) return null;
  const { id, title, created_at, expires_at, verified_count, total_claims, outcome, file_kind, file_count } = raw;
  if (typeof id !== "string" || !isRealReportId(id)) return null;
  if (!instant(created_at) || !instant(expires_at)) return null;
  if (!whole(verified_count) || !whole(total_claims) || verified_count > total_claims) return null;
  if (outcome !== "answered" && outcome !== "partial") return null;
  if (file_kind !== "csv" && file_kind !== "pdf" && file_kind !== null) return null;
  if (!whole(file_count)) return null;
  const clean = plainText(title, maxTitle);
  if (clean === "") return null;
  return { id, title: clean, createdAt: created_at, expiresAt: expires_at, verified: verified_count, total: total_claims, outcome, fileKind: file_kind, fileCount: file_count };
}

export function parseReportsPage(raw: unknown): ReportsPage | null {
  if (!object(raw) || !Array.isArray(raw.items)) return null;
  const cursor = raw.next_cursor;
  if (cursor !== null && (typeof cursor !== "string" || cursor === "" || cursor.length > maxCursor)) return null;
  const items = raw.items.flatMap((item) => {
    const row = parseReportRow(item);
    return row ? [row] : [];
  });
  return { items, nextCursor: cursor };
}

const kinds: Record<string, FileRow["kind"]> = { "text/csv": "csv", "application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png", "text/plain": "txt" };

export function parseFileRow(raw: unknown): FileRow | null {
  if (!object(raw)) return null;
  const { id, filename, mime, size, page_count, row_count, status, expires_at } = raw;
  if (typeof id !== "string" || !isRealReportId(id)) return null;
  const kind = typeof mime === "string" ? kinds[mime] : undefined;
  if (!kind || !whole(size) || !instant(expires_at)) return null;
  if (status !== "uploaded" && status !== "ready" && status !== "deleted") return null;
  if ((page_count !== null && !whole(page_count)) || (row_count !== null && !whole(row_count))) return null;
  const name = plainText(filename, maxName);
  if (name === "") return null;
  return { id, name, kind, size, pages: page_count, rows: row_count, deleted: status === "deleted", expiresAt: expires_at };
}

export function parseFiles(raw: unknown): FileRow[] | null {
  if (!Array.isArray(raw)) return null;
  return raw.flatMap((item) => {
    const row = parseFileRow(item);
    return row ? [row] : [];
  });
}

// These throw the ApiError of the client; a body of the wrong shape throws too, so the screen shows its error state.
export async function loadReports(cursor: string | null, signal?: AbortSignal, request: Request = defaultRequest): Promise<ReportsPage> {
  const query = new URLSearchParams({ limit: String(pageSize) });
  if (cursor) query.set("cursor", cursor);
  const page = parseReportsPage(await request<unknown>(`/api/reports?${query}`, { signal }));
  if (!page) throw new ApiError(200, "UNKNOWN");
  return page;
}

export async function loadFiles(signal?: AbortSignal, request: Request = defaultRequest): Promise<FileRow[]> {
  const files = parseFiles(await request<unknown>("/api/uploads?limit=100&include_deleted=true", { signal }));
  if (!files) throw new ApiError(200, "UNKNOWN");
  return files;
}

async function remove(path: string, request: Request): Promise<void> {
  try {
    await request(path, { method: "DELETE" });
  } catch (error) {
    if (!alreadyGone(error)) throw error;
  }
}

export const deleteReport = (id: string, request: Request = defaultRequest) => remove(`/api/reports/${encodeURIComponent(id)}`, request);
export const deleteFile = (id: string, request: Request = defaultRequest) => remove(`/api/uploads/${encodeURIComponent(id)}`, request);

// Key under `apiErrors`: the code of the API error (RUN_IN_PROGRESS, UPLOAD_IN_USE, NETWORK, ...), or UNKNOWN for anything else.
export function errorKey(error: unknown): ApiErrorCode {
  return error instanceof ApiError ? error.code : "UNKNOWN";
}

// A delete that answers 404 means the record is already gone, which is what the person asked for.
export const alreadyGone = (error: unknown): boolean => error instanceof ApiError && error.status === 404;

// Whole hours left until a file is deleted, rounded up and never below 1. Null once the time has passed.
export function hoursLeft(expiresAt: string, now: number): number | null {
  const ms = Date.parse(expiresAt) - now;
  return ms > 0 ? Math.max(1, Math.ceil(ms / 3_600_000)) : null;
}
