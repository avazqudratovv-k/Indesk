import { useTranslations } from "next-intl";
import type { Claim, Report } from "@/lib/types";
import { isProven } from "@/lib/report/view";
import styles from "./ConfidenceCard.module.css";

// "How sure are we?": the level from the report, one segment per claim (green proven, red not proven).
// Hidden when the report has no confidence (the critic did not run).
export default function ConfidenceCard({ report, claims }: { report: Report; claims: Claim[] }) {
  const t = useTranslations("report");
  if (!report.confidence) return null;
  const { verified_count: verified, total_claims: total } = report;
  const ordered = [...claims].sort((a, b) => a.n - b.n);
  return (
    <section className={styles.card}>
      <div className={styles.text}>
        <div className={styles.title}>{t("simple.confTitle")}</div>
        <div className={`${styles.level} ${styles[report.confidence]}`}>
          {t(`confidence.${report.confidence}`)} · {verified}/{total}
        </div>
        <div className={styles.note}>{t("simple.confNote", { total, verified, open: total - verified })}</div>
      </div>
      <div className={styles.bar} role="img" aria-label={t("simple.confBar", { verified, total })}>
        {ordered.map((claim) => (
          <span key={claim.id} className={`${styles.segment} ${isProven(claim.status) ? styles.segOk : styles.segBad}`} />
        ))}
      </div>
    </section>
  );
}
