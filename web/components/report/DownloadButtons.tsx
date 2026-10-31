"use client";

import { useTranslations } from "next-intl";
import type { ReportBundle } from "@/lib/report/get-report";
import { buildReportMarkdown, reportFileName } from "@/lib/report/real/markdown";
import styles from "./DownloadButtons.module.css";

// "Download PDF" prints the page (the print stylesheet makes it look like the report card); "Download .md" saves a Markdown
// file built here from the report already loaded. Neither calls the server.
export default function DownloadButtons({ bundle }: { bundle: ReportBundle }) {
  const t = useTranslations("report");
  const say = t as unknown as (key: string, values?: Record<string, string | number>) => string;

  // Chrome names the PDF after document.title. The page is printed in the light theme whatever the screen uses; both are
  // put back when the print dialog closes.
  function printPage() {
    const root = document.documentElement;
    const title = document.title;
    const theme = root.getAttribute("data-theme");
    document.title = bundle.report.title;
    root.setAttribute("data-theme", "light");
    window.addEventListener(
      "afterprint",
      () => {
        document.title = title;
        if (theme === null) root.removeAttribute("data-theme");
        else root.setAttribute("data-theme", theme);
      },
      { once: true },
    );
    window.print();
  }

  function saveMarkdown() {
    const blob = new Blob([buildReportMarkdown(bundle, say)], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = reportFileName(bundle.report.title, new Date());
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className={styles.group} data-print="hide">
      <button type="button" className={styles.primary} onClick={printPage}>
        {t("download.pdf")}
      </button>
      <button type="button" className={styles.link} onClick={saveMarkdown}>
        {t("download.md.button")}
      </button>
    </div>
  );
}
