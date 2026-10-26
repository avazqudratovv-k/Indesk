import { useTranslations } from "next-intl";
import type { AgentState, RunAgent } from "@/lib/run/mock-run";
import AgentRing from "./run/AgentRing";
import styles from "./AgentEndings.module.css";

// Board block "How each agent can end" (Ask tab): one example card per state. Reference only, so the Retry
// button of the Failed card is left out (the real Retry is in the live run, on the failure bar).
const examples: [RunAgent, AgentState][] = [
  ["owl", "done"],
  ["chameleon", "skipped"],
  ["beaver", "working"],
  ["hound", "failed"],
  ["cat", "waiting"],
];

export default function AgentEndings() {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  return (
    <section className={styles.sec} aria-labelledby="ws-ends-title">
      <div>
        <h2 id="ws-ends-title" className={styles.title}>
          {t("live.ends.title")}
        </h2>
        <p className={styles.sub}>{t("live.ends.sub")}</p>
      </div>
      <ul className={styles.grid} aria-label={t("live.ends.listLabel")}>
        {examples.map(([agent, state]) => (
          <li key={agent} className={styles.card}>
            <AgentRing agent={agent} state={state} />
            <span className={styles.example}>{t("live.outcomes.exampleTag")}</span>
            <div className={styles.name}>{home(`${agent}.name`)}</div>
            <span className={`${styles.pill} ${styles[state]}`}>{t(`live.status.${state}`)}</span>
            <p className={styles.line}>{t(`live.ends.lines.${state}`)}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
