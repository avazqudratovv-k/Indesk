import { useTranslations } from "next-intl";
import styles from "./Glossary.module.css";

const terms = ["verified", "unverified", "evidence"] as const;

// Detailed only: the three words a reader may not know. A real report has its own definitions: its checks are done in
// code against the computed table, not by finding a quote in a document.
export default function Glossary({ real = false }: { real?: boolean }) {
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
            <dd className={styles.def}>{t(real ? `glossReal.${term}` : `gloss.${term}.def`)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
