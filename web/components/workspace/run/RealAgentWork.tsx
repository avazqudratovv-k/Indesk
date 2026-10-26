"use client";

import { useId, useState } from "react";
import { useTranslations } from "next-intl";
import { RUN_AGENTS, type AgentView, type RunAgent, type RunEvent } from "@/lib/run/mock-run";
import AgentTabs, { panelId, tabId } from "./AgentTabs";
import { tabStatus } from "./agent-status";
import work from "./AgentWork.module.css";
import styles from "./RealAgentWork.module.css";

type Props = { agents: Record<RunAgent, AgentView>; events: RunEvent[]; finished: boolean };

// The agent shown while nobody was picked: the one that failed, else the agent of the newest line.
function autoAgent(events: RunEvent[], agents: Record<RunAgent, AgentView>, finished: boolean): RunAgent {
  if (finished) {
    const failed = RUN_AGENTS.find((id) => agents[id].state === "failed");
    if (failed) return failed;
  }
  return events.length > 0 ? events[events.length - 1].agent : "owl";
}

// Board section "What each agent actually did", for a real run. The scripted views (code, tables, passages) are mock
// content and are not shown here: each tab lists that agent's own trace lines, and says that results come with the
// report. The "not connected yet" line is temporary and goes away with the report screen (4.4).
export default function RealAgentWork({ agents, events, finished }: Props) {
  const t = useTranslations("workspace");
  const prefix = useId();
  const [pinned, setPinned] = useState<RunAgent | null>(null);
  const selected = pinned ?? autoAgent(events, agents, finished);
  const status = tabStatus(agents[selected], finished);
  const lines = events.filter((event) => event.agent === selected);

  return (
    <section className={work.sec} aria-labelledby={`${prefix}-title`}>
      <div className={work.head}>
        <div>
          <h2 id={`${prefix}-title`} className={work.title}>
            {t("artifacts.title")}
          </h2>
          <p className={work.sub}>{pinned ? t("artifacts.followPinned") : t("artifacts.followActive")}</p>
        </div>
        {pinned ? (
          <button type="button" className={work.follow} onClick={() => setPinned(null)}>
            {t("artifacts.followBtn")}
          </button>
        ) : null}
      </div>
      <AgentTabs agents={agents} finished={finished} selected={selected} idPrefix={prefix} onPick={setPinned} />
      <div id={panelId(prefix)} role="tabpanel" aria-labelledby={tabId(prefix, selected)} tabIndex={0} className={work.panel}>
        {lines.length > 0 ? (
          <ol className={styles.lines} aria-label={t("real.detail.linesLabel")}>
            {lines.map((line, index) => (
              <li key={`${index}-${line.key}`} className={`${styles.line} ${line.state === "failed" ? styles.lineFailed : ""}`}>
                {line.text}
              </li>
            ))}
          </ol>
        ) : status === "didNotRun" ? (
          <p className={work.state}>{t("artifacts.states.didNotRun")}</p>
        ) : (
          <p className={work.state}>{status === "waiting" ? t("artifacts.states.waiting") : t("real.detail.empty")}</p>
        )}
        <p className={styles.later}>{t("real.detail.later")}</p>
      </div>
    </section>
  );
}
