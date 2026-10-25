"use client";

import Link from "next/link";
import { useRef, useState, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/use-session";
import type { PlanOffer } from "@/lib/types";
import AskPanel, { type RunSummary } from "./AskPanel";
import RunTab from "./RunTab";
import SignedOutCard from "./SignedOutCard";
import styles from "./WorkspaceView.module.css";

type Tab = "ask" | "run";
const tabs: Tab[] = ["ask", "run"];

// The Workspace screen (ROADMAP 2.5): tabs, heading, usage pill and the Ask tab. The run tab is a placeholder until 2.6.
export default function WorkspaceView({ offers }: { offers: PlanOffer[] }) {
  const t = useTranslations("workspace");
  const session = useSession();
  const [tab, setTab] = useState<Tab>("ask");
  const [run, setRun] = useState<RunSummary | null>(null);
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
        {session.signedIn ? <AskPanel freeRuns={plan === "free" ? (offer?.runs ?? null) : null} plan={plan} onRun={(summary) => { setRun(summary); setTab("run"); }} /> : <SignedOutCard />}
      </div>

      <div id="ws-panel-run" role="tabpanel" aria-labelledby="ws-tab-run" hidden={tab !== "run"} className={styles.panel}>
        <RunTab run={run} onBack={() => { setTab("ask"); buttons.current[0]?.focus(); }} />
      </div>
    </main>
  );
}
