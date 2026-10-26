"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale } from "next-intl";
import RoutePlaceholder from "@/components/RoutePlaceholder";
import { langNote, loadReport, loadReportLang, type ReportLang, type ReportLoad } from "@/lib/report/real/api";
import ReportLoading from "./ReportLoading";
import ReportMessage from "./ReportMessage";
import ReportNotFound from "./ReportNotFound";
import ReportView from "./ReportView";

// A real report (ROADMAP 4.4): GET /api/reports/{id} through the same-origin /api proxy, in the browser, so the session
// cookie and its refresh work as on every other screen. The language note needs one more read (the run) and never
// blocks the report: if it fails, no note is shown.
export default function RealReport({ id }: { id: string }) {
  const locale = useLocale();
  const [attempt, setAttempt] = useState(0);
  // The answer belongs to one (id, attempt) pair; any other pair means "still loading", so nothing is reset in the effect.
  const key = `${id}:${attempt}`;
  const [answer, setAnswer] = useState<{ key: string; load: ReportLoad; lang: ReportLang | null } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void loadReport(id, controller.signal).then((load) => {
      if (controller.signal.aborted) return;
      setAnswer({ key, load, lang: null });
      if (load.status === "ready") {
        void loadReportLang(load.bundle.report.run_id, controller.signal).then((lang) => {
          if (!controller.signal.aborted) setAnswer((current) => (current?.key === key ? { ...current, lang } : current));
        });
      }
    });
    return () => controller.abort();
  }, [id, key]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  if (answer === null || answer.key !== key) return <ReportLoading />;
  const { load, lang } = answer;
  if (load.status === "notFound") return <ReportNotFound />;
  if (load.status === "unauthorized" || load.status === "error") return <ReportMessage kind={load.status} reportId={id} onRetry={retry} />;
  if (load.bundle.report.mode !== "ask") return <RoutePlaceholder route="Report" param={id} />;
  return <ReportView bundle={load.bundle} real={{ lang, note: langNote(lang, locale) }} />;
}
