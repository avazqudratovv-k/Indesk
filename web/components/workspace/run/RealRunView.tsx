"use client";

import { useEffect, useMemo, useRef } from "react";
import { useTranslations } from "next-intl";
import { isSimulated, toRunEvents } from "@/lib/run/live/agents";
import type { LiveRun } from "@/lib/run/live/reducer";
import { endCard } from "@/lib/run/live/reasons";
import { describeTrace } from "@/lib/run/live/trace";
import type { LiveStep, Outcome } from "@/lib/run/live/types";
import { countAgentsDone, countToolCalls, deriveAgents, RUN_AGENTS, sumTokens, type AgentView, type RunAgent } from "@/lib/run/mock-run";
import type { Connection } from "./use-live-run";
import AgentTimeline from "./AgentTimeline";
import GuardrailsPanel from "./GuardrailsPanel";
import LiveTrace from "./LiveTrace";
import OutcomeCards from "./OutcomeCards";
import RealAgentWork from "./RealAgentWork";
import RunEndCard, { RunNotice } from "./RunEndCard";
import RunHeader from "./RunHeader";
import RunTiles from "./RunTiles";
import TeamStage from "./TeamStage";
import styles from "./RunLive.module.css";

type Props = { run: LiveRun; connection: Connection; onReconnect: () => void; onBack: () => void };

// Once a run is over, an agent still shown as working can never finish (its worker is gone): it ends as failed when the
// run did not succeed, otherwise as done. A spinner never keeps turning on a finished run.
function settle(agents: Record<RunAgent, AgentView>, outcome: Outcome): Record<RunAgent, AgentView> {
  const ok = outcome === "answered" || outcome === "partial";
  const next = { ...agents };
  for (const id of RUN_AGENTS) if (next[id].state === "working") next[id] = { ...next[id], state: ok ? "done" : "failed" };
  return next;
}

// The live view of a real Ask run: the existing run components, fed with the run's own events. Nothing here is
// scripted: counts come from events, the text of each line from message keys (never from the server), and a stub run
// is labelled as simulated.
export default function RealRunView({ run, connection, onReconnect, onBack }: Props) {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  const heading = useRef<HTMLHeadingElement>(null);
  const endHeading = useRef<HTMLHeadingElement>(null);
  const wasFinished = useRef(run.done !== null);

  const message = t as unknown as (key: string, values?: Record<string, string | number>) => string;
  const describe = useMemo(
    () => (step: LiveStep) => {
      const text = describeTrace(step.key, step.args);
      const values = { ...text.values };
      if (typeof values.reason === "string") values.reason = message(`reasons.${values.reason}.head`);
      return message(`trace.${text.id}`, values);
    },
    // `t` changes with the language only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );

  const events = useMemo(() => toRunEvents(run.steps, describe), [run.steps, describe]);
  const finished = run.done !== null;
  const step = events.length;
  const agents = useMemo(() => {
    const raw = deriveAgents(events, step);
    return run.done ? settle(raw, run.done.outcome) : raw;
  }, [events, step, run.done]);
  const simulated = isSimulated(run.steps);
  const card = run.done ? endCard(run.done.outcome, run.done.reason) : null;
  const lost = !finished && connection !== "live";

  useEffect(() => {
    heading.current?.focus();
  }, []);

  // When the run ends while the person is watching, move focus to the result.
  useEffect(() => {
    if (finished && !wasFinished.current) endHeading.current?.focus();
    wasFinished.current = finished;
  }, [finished]);

  const ok = card?.kind === "report";
  const mark = card ? (ok ? { tone: card.outcome === "answered" ? ("ok" as const) : ("warn" as const), text: t("real.mark.finished") } : { tone: "bad" as const, text: t("real.mark.failed") }) : null;
  const latest = events.length > 0 ? events[events.length - 1] : null;
  const announcement = lost
    ? t("real.announce.lost")
    : card
      ? ok
        ? t("real.announce.finishedNoReport")
        : `${t("real.announce.failed")} ${message(`reasons.${card.reason}.head`)}`
      : latest
        ? `${home(`${latest.agent}.name`)}: ${latest.text ?? ""}`
        : events.length === 0 && run.status === "queued"
          ? t("real.announce.queued")
          : t("real.announce.running");

  const toolCalls = countToolCalls(events, step);

  return (
    <div className={styles.run}>
      {simulated ? (
        <p className={styles.banner}>
          <span className={styles.bannerTag}>{t("real.simulatedTag")}</span>
          {t("real.simulatedBanner")}
        </p>
      ) : null}
      <RunHeader ref={heading} title={run.question} finished={finished} onBack={onBack} real={{ mark }} />
      <RunTiles key={run.id} toolCalls={toolCalls} tokens={sumTokens(events, step)} agentsDone={countAgentsDone(agents)} agentCount={RUN_AGENTS.length} finished={finished} real={{ startMs: run.createdAt ?? run.startedAt, endMs: run.finishedAt }} />
      {lost ? <RunNotice signedOut={connection === "signedOut"} onReconnect={onReconnect} /> : null}
      {card ? <RunEndCard card={card} headingRef={endHeading} onChange={onBack} /> : null}
      {!finished && !lost && events.length === 0 ? (
        <p className={styles.note} role="status">
          {t("real.queued")}
        </p>
      ) : null}
      <section className={styles.team}>
        <div className={styles.stage}>
          <div className={styles.stageHead}>
            <h2 className={styles.h2}>{t("live.stageTitle")}</h2>
            <span className={styles.note}>{t("live.stageNote")}</span>
          </div>
          <TeamStage agents={agents} events={events} step={step} reportReady={false} scenario="answered" finished={finished} showStamp={false} />
          <AgentTimeline agents={agents} reportReady={false} finished={finished} />
        </div>
        <LiveTrace events={events} step={step} note={simulated ? t("real.simulatedTraceNote") : t("real.traceNote")} />
      </section>
      <p className={styles.srOnly} role="status" aria-live="polite">
        {announcement}
      </p>
      <GuardrailsPanel />
      <RealAgentWork key={`work-${run.id}`} agents={agents} events={events} finished={finished} />
      <OutcomeCards real />
    </div>
  );
}

