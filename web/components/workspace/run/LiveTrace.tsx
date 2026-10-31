import { useTranslations } from "next-intl";
import type { RunEvent } from "@/lib/run/mock-run";
import styles from "./LiveTrace.module.css";

const SHOWN = 8;

// Board "Live trace" card: the last 8 events, newest last, each with the agent's small icon; tool calls use the mono
// font and a flag has a red row. The list itself is not a live region (it would re-read everything each time):
// RunLive announces only the newest line through one status element.
export default function LiveTrace({ events, step, note }: { events: RunEvent[]; step: number; note?: string }) {
  const t = useTranslations("workspace");
  // Event keys come from the run (scripted or server), so the type cannot list them; the cast below is for that.
  const home = useTranslations("home.team");
  const shown = events.slice(0, step).slice(-SHOWN);
  return (
    <section className={styles.trace} aria-labelledby="ws-trace-title">
      <h2 id="ws-trace-title" className={styles.title}>
        {t("live.feedTitle")}
      </h2>
      <p className={styles.note}>{note ?? t("live.traceNote")}</p>
      {shown.length === 0 ? (
        <p className={styles.empty}>{t("live.feedEmpty")}</p>
      ) : (
        <ol className={styles.list} aria-label={t("live.feedLabel")}>
          {shown.map((event, index) => {
            const flag = event.kind === "flag";
            return (
              <li key={`${step - shown.length + index}-${event.key}`} className={`${styles.row} ${flag ? styles.flag : ""}`}>
                <span className={styles.icon}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={`/workspace/agent-${event.agent}.png`} alt="" width={20} height={20} />
                </span>
                <span className={event.kind === "say" ? styles.say : styles.tool}>{event.text ?? t(`live.events.${event.key}` as Parameters<typeof t>[0])}</span>
                <span className={styles.srOnly}>{home(`${event.agent}.name`)}</span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
