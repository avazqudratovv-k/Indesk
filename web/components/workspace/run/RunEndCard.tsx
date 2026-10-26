import type { Ref } from "react";
import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { isRealReportId } from "@/lib/report/real/id";
import type { EndCard } from "@/lib/run/live/reasons";
import styles from "./RunEndCard.module.css";

type Props = { card: EndCard; reportId: string | null; headingRef: Ref<HTMLHeadingElement>; onChange: () => void };

// How a real run ended (board "How a run can end"): a failure or rejection with a generic message for its reason code,
// or, for a run that finished with a report, a link to it (no automatic redirect, so the trace can still be read). A
// finished run with no usable report id says so. Nothing is claimed as verified, and the text never comes from the server.
export default function RunEndCard({ card, reportId, headingRef, onChange }: Props) {
  const t = useTranslations("workspace");
  // Keys are built from closed lists (reasons.ts, the outcome enum); the message types cannot see that.
  const message = t as unknown as (key: string) => string;

  if (card.kind === "report") {
    const href = reportId !== null && isRealReportId(reportId) ? `/reports/${reportId}` : null;
    return (
      <section className={`${styles.card} ${styles.stripe} ${card.outcome === "answered" ? styles.stripe_ok : styles.stripe_warn}`} aria-labelledby="ws-end-title">
        <div className={styles.top}>
          <span className={`${styles.label} ${card.outcome === "answered" ? styles.ok : styles.warn}`}>{t("real.mark.finished")}</span>
        </div>
        <h2 id="ws-end-title" ref={headingRef} tabIndex={-1} className={styles.head}>
          {href ? t("real.ready.title") : t("real.noReport.title")}
        </h2>
        <p className={styles.body}>{href ? t("real.ready.body") : t("real.noReport.body")}</p>
        {href ? (
          <div className={styles.actions}>
            <Button href={href} variant="ink">
              {t("real.ready.open")}
            </Button>
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <section className={`${styles.card} ${styles.stripe} ${styles[`stripe_${card.tone}`]}`} aria-labelledby="ws-end-title">
      <div className={styles.top}>
        <span className={`${styles.label} ${styles[card.tone]}`}>{message(`real.end.${card.label}`)}</span>
        {card.freeRunNote ? <span className={styles.count}>{t("real.end.notCounted")}</span> : null}
      </div>
      <h2 id="ws-end-title" ref={headingRef} tabIndex={-1} className={styles.head}>
        {message(`reasons.${card.reason}.head`)}
      </h2>
      <p className={styles.body}>{message(`reasons.${card.reason}.body`)}</p>
      {card.freeRunNote ? <p className={styles.note}>{t("real.end.freeRunNote")}</p> : null}
      <div className={styles.actions}>
        <button type="button" className={styles.action} onClick={onChange}>
          {t("real.end.newQuestion")}
        </button>
      </div>
    </section>
  );
}

// The stream was lost, or the session ended while following a run. The run itself may still be going.
export function RunNotice({ cause, onReconnect }: { cause: "lost" | "signedOut" | "tooManyStreams"; onReconnect: () => void }) {
  const t = useTranslations("workspace");
  return (
    <div className={styles.notice} role="alert">
      <div className={styles.noticeText}>
        <b>{t("real.lost.title")}</b>
        <span>{cause === "signedOut" ? t("real.lost.signedOut") : cause === "tooManyStreams" ? t("real.lost.tooManyStreams") : t("real.lost.body")}</span>
      </div>
      {cause === "signedOut" ? <Button href="/login">{t("real.lost.login")}</Button> : <Button onClick={onReconnect}>{t("real.lost.button")}</Button>}
    </div>
  );
}
