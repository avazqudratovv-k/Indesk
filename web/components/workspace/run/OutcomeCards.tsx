import { useTranslations } from "next-intl";
import styles from "./OutcomeCards.module.css";

type Outcome = { id: "answered" | "partial" | "notAnswerable" | "needsBetterInput" | "rejected" | "failed"; tone: string; counted: boolean };

// The six run outcomes of the board ("How a run can end"). The Check and Compare outcomes arrive with 2.10 and 2.11.
// Reference cards: the board's buttons are left out because nothing here can act on them.
const outcomes: Outcome[] = [
  { id: "answered", tone: "ok", counted: true },
  { id: "partial", tone: "warn", counted: true },
  { id: "notAnswerable", tone: "accent", counted: false },
  { id: "needsBetterInput", tone: "warn", counted: false },
  { id: "rejected", tone: "bad", counted: false },
  { id: "failed", tone: "neutral", counted: false },
];

export default function OutcomeCards() {
  const t = useTranslations("workspace");
  return (
    <section className={styles.sec} aria-labelledby="ws-outcomes-title">
      <div>
        <h2 id="ws-outcomes-title" className={styles.title}>
          {t("live.outcomes.title")}
        </h2>
        <p className={styles.sub}>{t("live.outcomes.sub")}</p>
      </div>
      <ul className={styles.grid}>
        {outcomes.map((outcome) => (
          <li key={outcome.id} className={styles.card}>
            <div className={styles.top}>
              <span className={`${styles.label} ${styles[outcome.tone]}`}>{t(`live.outcomes.${outcome.id}.label`)}</span>
              <span className={styles.count}>{outcome.counted ? t("live.outcomes.counted") : t("live.outcomes.notCounted")}</span>
            </div>
            <div className={styles.head}>{t(`live.outcomes.${outcome.id}.head`)}</div>
            <p className={styles.body}>{t(`live.outcomes.${outcome.id}.body`)}</p>
            {outcome.id === "notAnswerable" ? (
              <ul className={styles.chips}>
                {(t.raw("live.outcomes.notAnswerable.chips") as string[]).map((chip) => (
                  <li key={chip} className={styles.chip}>
                    {chip}
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
