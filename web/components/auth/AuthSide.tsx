import { useTranslations } from "next-intl";
import { MAX_CSV_ROWS, MAX_FILE_MB } from "@/lib/limits";
import { DemoNoticeText } from "./DemoNoticeText";
import styles from "./AuthSide.module.css";

function asStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

// Right-hand dark photo panel: what the free plan includes, how data is protected, and the demo notice.
export default function AuthSide() {
  const t = useTranslations("auth");
  return (
    <aside className={`dk ${styles.side}`}>
      <section className={styles.card} aria-labelledby="auth-free">
        <h2 id="auth-free" className={styles.freeTitle}>
          {t("freeTitle")}
        </h2>
        {[t("free.runs"), t("free.size", { mb: MAX_FILE_MB }), t("free.rows", { rows: MAX_CSV_ROWS })].map((text) => (
          <p key={text} className={styles.freeRow}>
            <span className={styles.tick}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12.5l5 5 9-10" />
              </svg>
            </span>
            {text}
          </p>
        ))}
      </section>
      <section className={styles.card} aria-labelledby="auth-trust">
        <h2 id="auth-trust" className={styles.trustTitle}>
          {t("trustTitle")}
        </h2>
        {asStrings(t.raw("trust")).map((text) => (
          <p key={text} className={styles.trustRow}>
            <svg className={styles.shield} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" />
            </svg>
            {text}
          </p>
        ))}
      </section>
      <DemoNoticeText className={styles.demo} />
    </aside>
  );
}
