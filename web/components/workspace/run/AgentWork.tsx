"use client";

import { useId, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { deriveArtifacts } from "@/lib/run/artifacts";
import { RUN_AGENTS, type AgentView, type RunAgent, type RunEvent, type RunScenario } from "@/lib/run/mock-run";
import AgentTabs, { panelId, tabId } from "./AgentTabs";
import BeaverView from "./BeaverView";
import CatView from "./CatView";
import ChameleonView from "./ChameleonView";
import HandoverCard from "./HandoverCard";
import HoundView from "./HoundView";
import OwlView from "./OwlView";
import { tabStatus } from "./agent-status";
import styles from "./AgentWork.module.css";

type Props = {
  agents: Record<RunAgent, AgentView>;
  events: RunEvent[];
  step: number;
  scenario: RunScenario;
  finished: boolean;
};

// The agent shown while nobody was picked: the agent of the newest event; once the run is over Cat, or the failed agent.
function autoAgent(events: RunEvent[], step: number, finished: boolean, agents: Record<RunAgent, AgentView>, scenario: RunScenario): RunAgent {
  // A run that stopped (failed scenario) opens on the agent that failed; every other finished run, partial included, opens on Cat.
  if (finished) return (scenario === "failed" && RUN_AGENTS.find((id) => agents[id].state === "failed")) || "cat";
  return step > 0 ? events[step - 1].agent : "owl";
}

// Board section "What each agent actually did". The only state is `pinned`: the agent the visitor picked, or null while
// the section follows the active agent. RunLive keys this component by run round, so Replay and Retry reset it.
export default function AgentWork({ agents, events, step, scenario, finished }: Props) {
  const t = useTranslations("workspace");
  const prefix = useId();
  const [pinned, setPinned] = useState<RunAgent | null>(null);
  const selected = pinned ?? autoAgent(events, step, finished, agents, scenario);
  const artifacts = useMemo(() => deriveArtifacts(events, step, scenario), [events, step, scenario]);
  const status = tabStatus(selected, agents[selected], finished);

  return (
    <section className={styles.sec} aria-labelledby={`${prefix}-title`}>
      <div className={styles.head}>
        <div>
          <h2 id={`${prefix}-title`} className={styles.title}>
            {t("artifacts.title")}
            <span className={styles.tag}>{t("live.tilesTag.example")}</span>
          </h2>
          <p className={styles.sub}>{pinned ? t("artifacts.followPinned") : t("artifacts.followActive")}</p>
        </div>
        {pinned ? (
          <button type="button" className={styles.follow} onClick={() => setPinned(null)}>
            {t("artifacts.followBtn")}
          </button>
        ) : null}
      </div>
      <AgentTabs agents={agents} finished={finished} selected={selected} idPrefix={prefix} onPick={setPinned} />
      <HandoverCard agent={selected} rows={artifacts.handover[selected]} />
      <div id={panelId(prefix)} role="tabpanel" aria-labelledby={tabId(prefix, selected)} tabIndex={0} className={styles.panel}>
        {status === "waiting" ? (
          <p className={styles.state}>{t("artifacts.states.waiting")}</p>
        ) : status === "didNotRun" ? (
          <p className={styles.state}>{t("artifacts.states.didNotRun")}</p>
        ) : status === "failed" ? (
          <p className={`${styles.state} ${styles.failed}`}>{t("artifacts.states.failed")}</p>
        ) : selected === "owl" ? (
          <OwlView artifacts={artifacts} finished={finished} />
        ) : selected === "cat" ? (
          <CatView artifacts={artifacts} />
        ) : selected === "chameleon" ? (
          <ChameleonView artifacts={artifacts} />
        ) : selected === "beaver" ? (
          <BeaverView artifacts={artifacts} />
        ) : (
          <HoundView artifacts={artifacts} finished={finished} />
        )}
      </div>
    </section>
  );
}
