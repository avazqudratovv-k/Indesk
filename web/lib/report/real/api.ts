import { ApiError } from "@/lib/api/errors";
import { apiClient } from "@/lib/api/client";
import type { ReportBundle } from "../get-report";
import { parseReportDetail } from "./parse";

// What the screen can be in after asking for a report. 404 is one state for a missing, expired, deleted or foreign report.
export type ReportLoad =
  | { status: "ready"; bundle: ReportBundle; lang: ReportLang | null }
  | { status: "notFound" }
  | { status: "unauthorized" }
  | { status: "error" };

type Request = <T>(path: string, init?: { signal?: AbortSignal }) => Promise<T>;

const defaultRequest: Request = <T,>(path: string, init?: { signal?: AbortSignal }) => apiClient().request<T>(path, init);

// Never throws: every failure is one of the states above, and no server text is kept.
export async function loadReport(id: string, signal?: AbortSignal, request: Request = defaultRequest): Promise<ReportLoad> {
  return loadFrom(`/api/reports/${encodeURIComponent(id)}`, signal, request);
}

async function loadFrom(path: string, signal: AbortSignal | undefined, request: Request): Promise<ReportLoad> {
  try {
    const raw = await request<unknown>(path, { signal });
    const bundle = parseReportDetail(raw);
    return bundle ? { status: "ready", bundle, lang: reportLang((raw as { report?: { lang?: unknown } }).report?.lang) } : { status: "error" };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 404) return { status: "notFound" };
      if (error.status === 401) return { status: "unauthorized" };
    }
    return { status: "error" };
  }
}

export type ReportLang = "en" | "ko";

// The language the report prose is written in: `report.lang` of the payload. Cat writes Korean when the run's language is
// Korean and English otherwise (api/app/runs/cat.py), so every other known code reads as English. Null when the field is
// missing or not a known code: the screen then shows no language note.
export function reportLang(value: unknown): ReportLang | null {
  if (value === "ko") return "ko";
  return value === "en" || value === "ja" || value === "ru" || value === "uz" ? "en" : null;
}

// The note appears only when the report language is known and differs from the site language.
export function langNote(reportLang: ReportLang | null, siteLocale: string): ReportLang | null {
  return reportLang !== null && reportLang !== siteLocale ? reportLang : null;
}

// The example report: GET /api/example, the same for everyone, no login. It is asked with refreshOn401 off and nothing
// else is requested, so a signed-out visitor never triggers a session refresh or any private endpoint.
export const EXAMPLE_PATH = "/api/example";
const exampleRequest: Request = <T,>(path: string, init?: { signal?: AbortSignal }) => apiClient().request<T>(path, { ...init, refreshOn401: false });

export async function loadExample(signal?: AbortSignal, request: Request = exampleRequest): Promise<ReportLoad> {
  return loadFrom(EXAMPLE_PATH, signal, request);
}
