"use client";

import Link from "next/link";
import { useRef, useState, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/use-session";
import { useUsage } from "@/hooks/use-usage";
import { freePill } from "@/lib/usage/api";
import type { RunScenario } from "@/lib/run/mock-run";
import type { PlanOffer } from "@/lib/types";
import AskPanel, { type RunSubmission, type RunSummary } from "./AskPanel";
import RealRunTab from "./RealRunTab";
import RunTab from "./RunTab";
import { useLiveRun } from "./run/use-live-run";
import SignedOutCard from "./SignedOutCard";
import styles from "./WorkspaceView.module.css";

type Tab = "ask" | "run";
const tabs: Tab[] = ["ask", "run"];

// The Workspace screen (ROADMAP 2.5, 2.6a): tabs, heading, usage pill, the Ask tab and the scripted run tab.
// Ask runs are real (ROADMAP 4.3): files are uploaded and the run is followed over the event stream.
// `mockOutcome` (dev only, set by the page) switches the tab back to the scripted demo run to look at a failed or partial case.
export default function WorkspaceView({ offers, mockOutcome }: { offers: PlanOffer[]; mockOutcome?: RunScenario }) {
  const t = useTranslations("workspace");
  const tCommon = useTranslations("common");
  const session = useSession();
  const [tab, setTab] = useState<Tab>("ask");
  const [run, setRun] = useState<RunSummary | null>(null);
  const [runKey, setRunKey] = useState(0);
  const [running, setRunning] = useState(false);
  const live = useLiveRun(session.signedIn ? session.user.id : null);
  const mockMode = mockOutcome !== undefined;
  const runLive = mockMode ? running : live.run !== null && live.run.done === null;
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const plan = session.user?.plan ?? "free";
  const offer = offers.find((entry) => entry.plan === plan);
  // The Free plan's counts come from GET /api/usage only. Until it answers (or if it fails) the pill names the plan and no number.
  // Asked again when a run starts or ends, or a run is refused; never on a timer.
  const serverUsage = useUsage(session.signedIn ? session.user.id : null, `${live.run?.id ?? ""}:${live.run?.done ? "done" : "open"}:${live.failure?.code ?? ""}`);
  const free = plan === "free" ? serverUsage?.free ?? null : null;
  const pill = freePill(serverUsage);
  const freeText = pill.key === "usage.free" ? t(pill.key, pill.values) : t(pill.key);
  const usage = !session.signedIn ? null : plan === "free" ? freeText : t(`usage.${plan}`, { runs: offer?.runs ?? 0 });

  async function onRun(submission: RunSubmission) {
    if (mockMode) {
      setRun({ mode: submission.mode, fileCount: submission.fileCount, question: submission.question });
      setRunKey((key) => key + 1);
      setTab("run");
      return;
    }
    if (submission.mode !== "ask") return;
    if (await live.start(submission.files, submission.question)) setTab("run");
  }

  function onKeyDown(event: KeyboardEvent, index: number) {
    const next =
      event.key === "ArrowRight" ? (index + 1) % tabs.length : event.key === "ArrowLeft" ? (index + tabs.length - 1) % tabs.length : event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    setTab(tabs[next]);
    buttons.current[next]?.focus();
  }

  return (
    <main className={styles.main}>
      <div className={styles.tabs} role="tablist" aria-label={t("tabsLabel")}>
        {tabs.map((value, index) => (
          <button
            key={value}
            ref={(node) => {
              buttons.current[index] = node;
            }}
            id={`ws-tab-${value}`}
            type="button"
            role="tab"
            className={styles.tab}
            aria-selected={tab === value}
            aria-controls={`ws-panel-${value}`}
            tabIndex={tab === value ? 0 : -1}
            onClick={() => setTab(value)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            <span className={styles.tabNumber}>{index + 1}</span>
            {t(value === "ask" ? "tabAsk" : "tabRun")}
            {value === "run" && runLive ? <span className={styles.liveDot} aria-hidden="true" /> : null}
          </button>
        ))}
      </div>

      <div id="ws-panel-ask" role="tabpanel" aria-labelledby="ws-tab-ask" hidden={tab !== "ask"} className={styles.panel}>
        <div className={styles.head}>
          <div className={styles.intro}>
            <h1 className={styles.title}>{t("title")}</h1>
            <p className={styles.sub}>{t("sub")}</p>
          </div>
          {usage ? (
            <Link href="/plans" className={styles.pill}>
              <span className={styles.pillDot} aria-hidden="true" />
              {usage}
            </Link>
          ) : null}
        </div>
        {session.status === "unknown" ? <p className={styles.sub} role="status">{tCommon("loading")}</p> : session.signedIn ? <AskPanel freeLeft={free ? free.left : null} plan={plan} onRun={onRun} submit={mockMode ? undefined : { stage: live.stage, progress: live.progress, fileStatus: live.fileStatus, failure: live.failure, activeRunId: live.activeRunId, followingRunId: live.run?.id ?? null, onWatchActive: () => void live.watchActive().then(() => setTab("run")), onFileRemoved: live.forgetFile, onDismissFailure: live.clearFailure }} /> : <SignedOutCard />}
      </div>

      <div id="ws-panel-run" role="tabpanel" aria-labelledby="ws-tab-run" hidden={tab !== "run"} className={styles.panel}>
        {mockMode ? (
          <RunTab run={run} runKey={runKey} scenario={mockOutcome} onBack={() => { setTab("ask"); buttons.current[0]?.focus(); }} onRunningChange={setRunning} />
        ) : (
          <RealRunTab live={live} onBack={() => { setTab("ask"); buttons.current[0]?.focus(); }} />
        )}
      </div>
    </main>
  );
}
