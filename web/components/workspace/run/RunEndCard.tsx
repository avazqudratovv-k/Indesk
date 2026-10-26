import type { Ref } from "react";
import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import type { EndCard } from "@/lib/run/live/reasons";
import styles from "./RunEndCard.module.css";

// The mock report the "example" link opens. It is labelled as an example everywhere it is offered.
const EXAMPLE_REPORT = "/reports/rep_01";

type Props = { card: EndCard; headingRef: Ref<HTMLHeadingElement>; onChange: () => void };

// How a real run ended (board "How a run can end"): a failure or rejection with a generic message for its reason code,
// or, for a run that finished with no report to open yet, an honest "finished, no report" card. Nothing is claimed as
// verified, and the text never comes from the server.
export default function RunEndCard({ card, headingRef, onChange }: Props) {
  const t = useTranslations("workspace");
  // Keys are built from closed lists (reasons.ts, the outcome enum); the message types cannot see that.
  const message = t as unknown as (key: string) => string;

  if (card.kind === "report") {
    return (
      <section className={`${styles.card} ${styles.stripe} ${card.outcome === "answered" ? styles.stripe_ok : styles.stripe_warn}`} aria-labelledby="ws-end-title">
        <div className={styles.top}>
          <span className={`${styles.label} ${card.outcome === "answered" ? styles.ok : styles.warn}`}>{t("real.mark.finished")}</span>
        </div>
        <h2 id="ws-end-title" ref={headingRef} tabIndex={-1} className={styles.head}>
          {t("real.noReport.title")}
        </h2>
        <p className={styles.body}>{t("real.noReport.body")}</p>
        <div className={styles.actions}>
          <Button href={EXAMPLE_REPORT}>{t("real.noReport.example")}</Button>
          <span className={styles.note}>{t("real.noReport.exampleNote")}</span>
        </div>
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
export function RunNotice({ signedOut, onReconnect }: { signedOut: boolean; onReconnect: () => void }) {
  const t = useTranslations("workspace");
  return (
    <div className={styles.notice} role="alert">
      <div className={styles.noticeText}>
        <b>{t("real.lost.title")}</b>
        <span>{signedOut ? t("real.lost.signedOut") : t("real.lost.body")}</span>
      </div>
      {signedOut ? <Button href="/login">{t("real.lost.login")}</Button> : <Button onClick={onReconnect}>{t("real.lost.button")}</Button>}
    </div>
  );
}
