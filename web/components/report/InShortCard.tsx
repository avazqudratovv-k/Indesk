import { useTranslations } from "next-intl";
import type { ReportSummary } from "@/lib/types";
import { useProseLang } from "./ProseLang";
import styles from "./InShortCard.module.css";

// "In short": the model's bullets. A verified bullet carries its number, a flagged one a "!" (meaning is never by colour alone).
export default function InShortCard({ items }: { items: NonNullable<ReportSummary["in_short"]> }) {
  const t = useTranslations("report.simple");
  const lang = useProseLang();
  return (
    <section className={styles.card} aria-labelledby="report-in-short">
      <h2 id="report-in-short" className={styles.title}>
        {t("inShort")}
      </h2>
      {items.map((item, index) => (
        <div key={index} className={styles.item}>
          <span className={`${styles.mark} ${item.status === "verified" ? styles.ok : styles.bad}`} aria-hidden="true">
            {item.status === "verified" ? index + 1 : "!"}
          </span>
          <span lang={lang}>{item.text}</span>
        </div>
      ))}
    </section>
  );
}
