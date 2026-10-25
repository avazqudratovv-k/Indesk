import { useTranslations } from "next-intl";
import section from "./HomeSection.module.css";
import styles from "./HomeTrust.module.css";

// These are product rules from the spec (docs/ai/SPEC.md), not statistics or certifications.
const keys = ["files", "sandbox", "evidence", "instructions"] as const;

export default function HomeTrust() {
  const t = useTranslations("home.trust");
  return (
    <section className={`${section.section} ${section.tight}`}>
      <ul className={styles.box}>
        {keys.map((key) => (
          <li key={key} className={styles.item}>
            <svg className={styles.icon} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" />
              <path d="M8.5 12l2.5 2.5 4.5-5" />
            </svg>
            {t(key)}
          </li>
        ))}
      </ul>
    </section>
  );
}
