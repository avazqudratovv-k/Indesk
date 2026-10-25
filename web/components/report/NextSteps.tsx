import { useTranslations } from "next-intl";
import styles from "./NextSteps.module.css";

export default function NextSteps({ steps }: { steps: string[] }) {
  const t = useTranslations("report.simple");
  return (
    <section className={styles.card} aria-labelledby="report-next">
      <h2 id="report-next" className={styles.title}>
        {t("nextTitle")}
      </h2>
      <ol className={styles.list}>
        {steps.map((step, index) => (
          <li key={step} className={styles.item}>
            <span className={styles.number} aria-hidden="true">
              {index + 1}
            </span>
            {step}
          </li>
        ))}
      </ol>
    </section>
  );
}
