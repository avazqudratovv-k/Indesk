import { useTranslations } from "next-intl";
import styles from "./Glossary.module.css";

const terms = ["verified", "unverified", "evidence"] as const;

// Detailed only: the three words a reader may not know.
export default function Glossary() {
  const t = useTranslations("report.detailed");
  return (
    <section className={styles.card} aria-labelledby="report-gloss">
      <h2 id="report-gloss" className={styles.title}>
        {t("glossTitle")}
      </h2>
      <dl className={styles.list}>
        {terms.map((term) => (
          <div key={term} className={styles.item}>
            <dt className={styles.term}>{t(`gloss.${term}.term`)}.</dt>
            <dd className={styles.def}>{t(`gloss.${term}.def`)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
