"use client";

import Link from "next/link";
import { useRef, useState, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/use-session";
import type { RunScenario } from "@/lib/run/mock-run";
import type { PlanOffer } from "@/lib/types";
import AskPanel, { type RunSummary } from "./AskPanel";
import RunTab from "./RunTab";
import SignedOutCard from "./SignedOutCard";
import styles from "./WorkspaceView.module.css";

type Tab = "ask" | "run";
const tabs: Tab[] = ["ask", "run"];

// The Workspace screen (ROADMAP 2.5, 2.6a): tabs, heading, usage pill, the Ask tab and the scripted run tab.
// `mockOutcome` (dev only, set by the page) picks a failed or partial scripted run.
export default function WorkspaceView({ offers, mockOutcome = "answered" }: { offers: PlanOffer[]; mockOutcome?: RunScenario }) {
  const t = useTranslations("workspace");
  const tCommon = useTranslations("common");
  const session = useSession();
  const [tab, setTab] = useState<Tab>("ask");
  const [run, setRun] = useState<RunSummary | null>(null);
  const [runKey, setRunKey] = useState(0);
  const [running, setRunning] = useState(false);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  const plan = session.user?.plan ?? "free";
  const offer = offers.find((entry) => entry.plan === plan);
  const usage = session.signedIn ? t(`usage.${plan}`, { runs: offer?.runs ?? 0 }) : null;

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
            {value === "run" && running ? <span className={styles.liveDot} aria-hidden="true" /> : null}
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
        {session.status === "unknown" ? <p className={styles.sub} role="status">{tCommon("loading")}</p> : session.signedIn ? <AskPanel freeRuns={plan === "free" ? (offer?.runs ?? null) : null} plan={plan} onRun={(summary) => { setRun(summary); setRunKey((key) => key + 1); setTab("run"); }} /> : <SignedOutCard />}
      </div>

      <div id="ws-panel-run" role="tabpanel" aria-labelledby="ws-tab-run" hidden={tab !== "run"} className={styles.panel}>
        <RunTab run={run} runKey={runKey} scenario={mockOutcome} onBack={() => { setTab("ask"); buttons.current[0]?.focus(); }} onRunningChange={setRunning} />
      </div>
    </main>
  );
}
