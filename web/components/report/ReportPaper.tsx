import { useTranslations } from "next-intl";
import type { Report } from "@/lib/types";
import styles from "./ReportPaper.module.css";

// Design B, the stamped document (board `.pb`): stamp, small label, title, summary, ruled rows and the result line.
// The stamp counts come from the report's verified_count and total_claims, never from text. With no claims (the critic
// did not run) there is no stamp (DESIGN.md honesty marks).
export default function ReportPaper({ report }: { report: Report }) {
  const t = useTranslations("report");
  const { verified_count: verified, total_claims: total, summary_json: summary } = report;
  return (
    <section className={styles.paper} aria-labelledby="report-title">
      {total > 0 ? (
        <div className={styles.stamp} role="img" aria-label={t("paper.stampAria", { verified, total })}>
          <span className={styles.stampLine}>{t("paper.stampWord")}</span>
          <span className={styles.stampLine}>{t("paper.stampCount", { verified, total })}</span>
        </div>
      ) : null}
      <small className={styles.small}>{t("paper.small")}</small>
      <h1 id="report-title" className={styles.title}>
        {report.title}
      </h1>
      <p className={styles.answer}>{summary.answer}</p>
      {(summary.top_rows ?? []).map((row) => (
        <div key={row.label} className={styles.row}>
          <span className={styles.label}>{row.label}</span>
          <b className={styles.value}>{row.value}</b>
          <em className={`${styles.status} ${row.status === "verified" ? styles.ok : styles.bad}`}>{t(row.status === "verified" ? "paper.rowMatches" : "paper.rowNotProven")}</em>
        </div>
      ))}
      <div className={styles.total}>
        <span>{t("paper.resultLabel")}</span>
        {report.confidence ? <span>{t(`confidence.${report.confidence}`)}</span> : null}
      </div>
    </section>
  );
}
