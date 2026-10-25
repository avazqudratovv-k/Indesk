import { useTranslations } from "next-intl";
import styles from "./ReportState.module.css";

export default function ReportLoading() {
  const t = useTranslations("report.states");
  return (
    <main className={styles.main}>
      <p className={styles.body} role="status">
        {t("loading")}
      </p>
    </main>
  );
}
