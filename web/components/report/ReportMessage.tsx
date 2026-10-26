import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { loginHref } from "@/lib/auth/safe-next";
import styles from "./ReportState.module.css";

type Props = { kind: "unauthorized" | "error"; reportId: string; onRetry: () => void };

// A real report that could not be shown: the session ended (log in again), or the request failed (try again). The text
// never comes from the server.
export default function ReportMessage({ kind, reportId, onRetry }: Props) {
  const t = useTranslations(`report.states.${kind}`);
  return (
    <main className={styles.main}>
      <section className={styles.card} role="alert">
        <h1 className={styles.title}>{t("title")}</h1>
        <p className={styles.body}>{t("body")}</p>
        <div className={styles.actions}>
          {kind === "unauthorized" ? <Button href={loginHref(`/reports/${reportId}`)}>{t("action")}</Button> : <Button onClick={onRetry}>{t("action")}</Button>}
        </div>
      </section>
    </main>
  );
}
