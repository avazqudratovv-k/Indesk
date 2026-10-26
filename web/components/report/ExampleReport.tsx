"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale } from "next-intl";
import RoutePlaceholder from "@/components/RoutePlaceholder";
import { langNote, loadExample, type ReportLoad } from "@/lib/report/real/api";
import ReportLoading from "./ReportLoading";
import ReportMessage from "./ReportMessage";
import ReportNotFound from "./ReportNotFound";
import ReportView from "./ReportView";

// The example report (GET /api/example): public, the same for everyone. It never reads the session and never calls a
// private endpoint, so a signed-out visitor sees it with no login prompt or refresh. Its id is the word "example";
// real report ids are database UUIDs, so the two can never be the same (lib/report/real/id.ts).
export default function ExampleReport() {
  const locale = useLocale();
  const [attempt, setAttempt] = useState(0);
  const [answer, setAnswer] = useState<{ attempt: number; load: ReportLoad } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void loadExample(controller.signal).then((load) => {
      if (!controller.signal.aborted) setAnswer({ attempt, load });
    });
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  if (answer === null || answer.attempt !== attempt) return <ReportLoading />;
  const { load } = answer;
  if (load.status === "notFound") return <ReportNotFound />;
  // "unauthorized" cannot happen for a public route; it is treated like any other failure, with no login prompt.
  if (load.status === "unauthorized" || load.status === "error") return <ReportMessage kind="error" reportId="example" onRetry={retry} />;
  if (load.bundle.report.mode !== "ask") return <RoutePlaceholder route="Report" param="example" />;
  return <ReportView bundle={load.bundle} example real={{ lang: load.lang, note: langNote(load.lang, locale) }} />;
}
