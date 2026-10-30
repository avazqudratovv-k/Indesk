"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { isRealReportId } from "@/lib/report/real/id";
import { RUN_AGENTS, type AgentView, type RunAgent, type RunEvent } from "@/lib/run/mock-run";
import AgentTabs, { panelId, tabId } from "./AgentTabs";
import { tabStatus } from "./agent-status";
import work from "./AgentWork.module.css";
import styles from "./RealAgentWork.module.css";

type Props = { agents: Record<RunAgent, AgentView>; events: RunEvent[]; finished: boolean; reportId: string | null };

// The agent shown while nobody was picked: the one that failed, else the agent of the newest line.
function autoAgent(events: RunEvent[], agents: Record<RunAgent, AgentView>, finished: boolean): RunAgent {
  if (finished) {
    const failed = RUN_AGENTS.find((id) => agents[id].state === "failed");
    if (failed) return failed;
  }
  return events.length > 0 ? events[events.length - 1].agent : "owl";
}

// Board section "What each agent actually did", for a real run. The scripted views (code, tables, passages) are mock
// content and are not shown here: each tab lists that agent's own trace lines, and links to the report once there is one.
export default function RealAgentWork({ agents, events, finished, reportId }: Props) {
  const t = useTranslations("workspace");
  const prefix = useId();
  const [pinned, setPinned] = useState<RunAgent | null>(null);
  const selected = pinned ?? autoAgent(events, agents, finished);
  const status = tabStatus(selected, agents[selected], finished, true);
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
      <AgentTabs agents={agents} finished={finished} selected={selected} idPrefix={prefix} real onPick={setPinned} />
      <div id={panelId(prefix)} role="tabpanel" aria-labelledby={tabId(prefix, selected)} tabIndex={0} className={work.panel}>
        {lines.length > 0 ? (
          <ol className={styles.lines} aria-label={t("real.detail.linesLabel")}>
            {lines.map((line, index) => (
              <li key={`${index}-${line.key}`} className={`${styles.line} ${line.state === "failed" ? styles.lineFailed : ""}`}>
                {line.text}
              </li>
            ))}
          </ol>
        ) : status === "comingLater" ? (
          <p className={work.state}>{t("artifacts.states.comingLater")}</p>
        ) : status === "notUsed" ? (
          <p className={work.state}>{t("artifacts.states.notUsed")}</p>
        ) : status === "didNotRun" ? (
          <p className={work.state}>{t("artifacts.states.didNotRun")}</p>
        ) : (
          <p className={work.state}>{status === "waiting" ? t("artifacts.states.waiting") : t("real.detail.empty")}</p>
        )}
        {reportId !== null && isRealReportId(reportId) ? (
          <p className={styles.later}>
            {t("real.detail.inReport")}{" "}
            <Link href={`/reports/${reportId}`} className={styles.reportLink}>
              {t("real.ready.open")}
            </Link>
          </p>
        ) : null}
      </div>
    </section>
  );
}
