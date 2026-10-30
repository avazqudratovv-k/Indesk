import { useTranslations } from "next-intl";
import styles from "@/components/report/ReportState.module.css";
import Button from "@/components/ui/Button";

// Root 404 (any URL that matches no route). The language comes from the NEXT_LOCALE cookie, like every page (i18n/request.ts).
export default function NotFound() {
  const t = useTranslations("notFound");
  return (
    <main className={styles.main}>
      <section className={styles.card}>
        <h1 className={styles.title}>{t("title")}</h1>
        <p className={styles.body}>{t("body")}</p>
        <div className={styles.actions}>
          <Button href="/" variant="ink">
            {t("home")}
          </Button>
        </div>
      </section>
    </main>
  );
}
