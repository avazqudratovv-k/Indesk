import { ApiError } from "@/lib/api/errors";
import { apiClient } from "@/lib/api/client";
import type { ReportBundle } from "../get-report";
import { parseReportDetail } from "./parse";

// What the screen can be in after asking for a report. 404 is one state for a missing, expired, deleted or foreign report.
export type ReportLoad =
  | { status: "ready"; bundle: ReportBundle }
  | { status: "notFound" }
  | { status: "unauthorized" }
  | { status: "error" };

type Request = <T>(path: string, init?: { signal?: AbortSignal }) => Promise<T>;

const defaultRequest: Request = <T,>(path: string, init?: { signal?: AbortSignal }) => apiClient().request<T>(path, init);

// Never throws: every failure is one of the states above, and no server text is kept.
export async function loadReport(id: string, signal?: AbortSignal, request: Request = defaultRequest): Promise<ReportLoad> {
  try {
    const raw = await request<unknown>(`/api/reports/${encodeURIComponent(id)}`, { signal });
    const bundle = parseReportDetail(raw);
    return bundle ? { status: "ready", bundle } : { status: "error" };
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.status === 404) return { status: "notFound" };
      if (error.status === 401) return { status: "unauthorized" };
    }
    return { status: "error" };
  }
}

export type ReportLang = "en" | "ko";

// The language the report prose is written in. Cat writes Korean when the run's language is Korean and English
// otherwise (api/app/runs/cat.py). The report itself carries no language, so it is read from the run (owner only).
// Null when the run cannot be read or its language is not a known code: the screen then shows no language note.
export async function loadReportLang(runId: string, signal?: AbortSignal, request: Request = defaultRequest): Promise<ReportLang | null> {
  try {
    const raw = await request<unknown>(`/api/runs/${encodeURIComponent(runId)}`, { signal });
    const lang = typeof raw === "object" && raw !== null ? (raw as { lang?: unknown }).lang : undefined;
    if (lang === "ko") return "ko";
    return lang === "en" || lang === "ja" || lang === "ru" || lang === "uz" ? "en" : null;
  } catch {
    return null;
  }
}

// The note appears only when the report language is known and differs from the site language.
export function langNote(reportLang: ReportLang | null, siteLocale: string): ReportLang | null {
  return reportLang !== null && reportLang !== siteLocale ? reportLang : null;
}
