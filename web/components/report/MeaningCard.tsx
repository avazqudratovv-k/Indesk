import { useTranslations } from "next-intl";
import { useProseLang } from "./ProseLang";
import styles from "./MeaningCard.module.css";

export default function MeaningCard({ text }: { text: string }) {
  const t = useTranslations("report.simple");
  const lang = useProseLang();
  return (
    <section className={styles.card} aria-labelledby="report-meaning">
      <h2 id="report-meaning" className={styles.title}>
        {t("meaningTitle")}
      </h2>
      <p className={styles.text} lang={lang}>
        {text}
      </p>
    </section>
  );
}
