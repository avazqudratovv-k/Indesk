import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import styles from "./ReportState.module.css";

// Unknown id, or a report that is deleted or not the user's: one plain state with the next steps.
export default function ReportNotFound() {
  const t = useTranslations("report.states.notFound");
  return (
    <main className={styles.main}>
      <section className={styles.card}>
        <h1 className={styles.title}>{t("title")}</h1>
        <p className={styles.body}>{t("body")}</p>
        <div className={styles.actions}>
          <Button href="/workspace" variant="ink">
            {t("workspace")}
          </Button>
          <Button href="/">{t("home")}</Button>
        </div>
      </section>
    </main>
  );
}
