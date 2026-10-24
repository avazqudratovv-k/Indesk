import { useTranslations } from "next-intl";
import styles from "./DemoNotice.module.css";

export default function DemoNotice() {
  const t = useTranslations("demoNotice");
  return (
    <p className={styles.notice} role="note">
      <svg className={styles.icon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 3l10 18H2z" />
        <path d="M12 10v5" />
        <path d="M12 18.2v.1" />
      </svg>
      <span>{t("text")}</span>
    </p>
  );
}
