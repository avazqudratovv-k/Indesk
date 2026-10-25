import { useTranslations } from "next-intl";
import styles from "./EnforceCard.module.css";

function asStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

// "How the limits are enforced": the design rules, with a note that this demo page enforces nothing.
export default function EnforceCard() {
  const t = useTranslations("plans.enforce");
  return (
    <section className={styles.card} aria-labelledby="plans-enforce">
      <h2 id="plans-enforce" className={styles.title}>
        {t("title")}
      </h2>
      <ul className={styles.list}>
        {asStrings(t.raw("items")).map((text) => (
          <li key={text} className={styles.item}>
            <svg className={styles.shield} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" />
            </svg>
            {text}
          </li>
        ))}
      </ul>
      <p className={styles.note}>{t("demoNote")}</p>
    </section>
  );
}
