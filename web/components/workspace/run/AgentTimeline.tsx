import type { CSSProperties } from "react";
import { useTranslations } from "next-intl";
import { RUN_AGENTS, type AgentView, type RunAgent } from "@/lib/run/mock-run";
import AgentSprite from "./AgentSprite";
import { endedKey } from "./agent-status";
import styles from "./AgentTimeline.module.css";

type Vars = CSSProperties & Record<`--${string}`, string>;

// The board's phone version of the team (".mob-block"): a vertical timeline with an animated mascot per agent and the
// Report at the end. It is also the text equivalent of the graph: a list of agent name and status. From 761 px the
// map shows the state visually and this list stays for assistive tech only.
export default function AgentTimeline({ agents, reportReady, finished }: { agents: Record<RunAgent, AgentView>; reportReady: boolean; finished: boolean }) {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  return (
    <ol className={styles.list} aria-label={t("live.timelineLabel")}>
      {RUN_AGENTS.map((id, index) => {
        const view = agents[id];
        const key = endedKey(view, finished);
        const live = view.state === "working" ? "on" : view.state === "waiting" ? "dim" : "";
        return (
          <li key={id} className={`${styles.item} ${styles[`s_${key === "didNotRun" ? "waiting" : key}`]}`}>
            <span className={styles.ring}>
              <AgentSprite agent={id} live={live} size={52} phase={index} className={styles.sprite} />
            </span>
            <span className={styles.text}>
              <b className={styles.name}>
                {home(`${id}.name`)} · {home(`${id}.role`)}
              </b>
              <span className={styles.status}>{key === "flagged" ? t("live.status.flagged", { count: view.flags }) : t(`live.status.${key}`)}</span>
            </span>
          </li>
        );
      })}
      <li className={`${styles.item} ${reportReady ? styles.s_done : styles.s_waiting}`} style={{ "--x": "0" } as Vars}>
        <span className={styles.reportMark}>¶</span>
        <span className={styles.text}>
          <b className={styles.name}>{t("live.reportNode.name")}</b>
          <span className={styles.status}>{t(reportReady ? "live.reportNode.ready" : finished ? "live.reportNode.notReached" : "live.reportNode.waiting")}</span>
        </span>
      </li>
    </ol>
  );
}
