import { useFormatter, useTranslations } from "next-intl";
import type { RunAgent } from "@/lib/run/mock-run";
import type { Artifacts, ResolvedValue } from "@/lib/run/artifacts";
import styles from "./HandoverCard.module.css";

// Board ".ws-hand": what the selected agent hands to the report, three values. A value shows a dash until the agent
// has produced it. Not a live region: RunLive's status line already announces each event.
export default function HandoverCard({ agent, rows }: { agent: RunAgent; rows: Artifacts["handover"][RunAgent] }) {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  const format = useFormatter();
  // Message keys and arguments come from the mock, so they cannot be checked against the message types here.
  const message = t as unknown as (key: string, values?: Record<string, string | number>) => string;

  function show(value: ResolvedValue): string {
    if (value === null) return "—";
    if ("number" in value) return format.number(value.number);
    if ("text" in value) return value.text;
    return message(`artifacts.${value.msg}`, value.args);
  }

  return (
    <div className={styles.card}>
      <div className={styles.head}>
        <b>
          {home(`${agent}.name`)} · {t("artifacts.handover.title")}
        </b>
        <span className={styles.sub}>{t("artifacts.handover.sub")}</span>
        <span className={styles.tag}>{t("live.tilesTag.example")}</span>
      </div>
      <dl className={styles.grid}>
        {rows.map((row) => (
          <div key={row.label}>
            <dt>{t(`artifacts.handover.labels.${row.label}`)}</dt>
            <dd>
              {show(row.value)}
              {row.value === null ? <span className={styles.srOnly}> ({t("artifacts.handover.none")})</span> : null}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
