"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";
import { countAgentsDone, RUN_AGENTS, sumTokens, type RunScenario } from "@/lib/run/mock-run";
import type { RunSummary } from "../AskPanel";
import AgentTimeline from "./AgentTimeline";
import AgentWork from "./AgentWork";
import FailureBar from "./FailureBar";
import GuardrailsPanel from "./GuardrailsPanel";
import LiveTrace from "./LiveTrace";
import OutcomeCards from "./OutcomeCards";
import RunHeader from "./RunHeader";
import RunTiles from "./RunTiles";
import TeamStage from "./TeamStage";
import { useMockRun } from "./use-mock-run";
import styles from "./RunLive.module.css";

type Props = {
  run: RunSummary;
  scenario: RunScenario;
  onBack: () => void;
  onRunningChange: (running: boolean) => void;
};

// The live view of a scripted Ask run (ROADMAP 2.6a). Mounted once per Run press (keyed by the parent), so switching
// tabs keeps it. Nothing is sent anywhere and nothing is computed from the user's files.
export default function RunLive({ run, scenario: initial, onBack, onRunningChange }: Props) {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  const mock = useMockRun(initial);
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    heading.current?.focus();
  }, []);

  const running = !mock.finished;
  useEffect(() => {
    onRunningChange(running);
    return () => onRunningChange(false);
  }, [running, onRunningChange]);

  const failedAgent = mock.finished ? (Object.entries(mock.agents).find(([, view]) => view.state === "failed")?.[0] as keyof typeof mock.agents | undefined) : undefined;
  const reportReady = mock.finished && mock.scenario !== "failed";
  const latest = mock.step > 0 ? mock.events[mock.step - 1] : null;
  // Event keys come from the run (scripted or server), so the type cannot list them; hence the cast.
  const announcement = mock.finished ? t(`live.finishedAnnounce.${mock.scenario}`) : latest ? `${home(`${latest.agent}.name`)}: ${t(`live.events.${latest.key}` as Parameters<typeof t>[0])}` : t("live.running");

  return (
    <div className={styles.run}>
      <p className={styles.banner}>
        <span className={styles.bannerTag} aria-hidden="true">{t("live.demoTag")}</span>
        {t("live.demoBanner")}
      </p>
      <RunHeader ref={heading} title={run.question} finished={mock.finished} scenario={mock.scenario} onBack={onBack} onReplay={mock.replay} />
      <RunTiles key={mock.round} toolCalls={mock.toolCalls} tokens={sumTokens(mock.events, mock.step)} agentsDone={countAgentsDone(mock.agents)} agentCount={RUN_AGENTS.length} finished={mock.finished} />
      {failedAgent ? <FailureBar agent={failedAgent} onRetry={mock.retry} /> : null}
      <section className={styles.team}>
        <div className={styles.stage}>
          <div className={styles.stageHead}>
            <h2 className={styles.h2}>{t("live.stageTitle")}</h2>
            <span className={styles.note}>{t("live.stageNote")}</span>
          </div>
          <TeamStage agents={mock.agents} events={mock.events} step={mock.step} reportReady={reportReady} scenario={mock.scenario} finished={mock.finished} />
          <AgentTimeline agents={mock.agents} reportReady={reportReady} finished={mock.finished} />
        </div>
        <LiveTrace events={mock.events} step={mock.step} />
      </section>
      <p className={styles.srOnly} role="status">
        {announcement}
      </p>
      <GuardrailsPanel />
      <AgentWork key={`work-${mock.round}`} agents={mock.agents} events={mock.events} step={mock.step} scenario={mock.scenario} finished={mock.finished} />
      <OutcomeCards />
    </div>
  );
}
