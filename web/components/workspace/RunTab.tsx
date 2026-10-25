"use client";

import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import type { RunScenario } from "@/lib/run/mock-run";
import type { RunSummary } from "./AskPanel";
import RunLive from "./run/RunLive";
import styles from "./RunTab.module.css";

type Props = {
  run: RunSummary | null;
  // Changes on every Run press, so a new run starts fresh while a tab switch keeps the current one.
  runKey: number;
  // Dev-only ?mockOutcome value; the page passes it only in development.
  scenario: RunScenario;
  onBack: () => void;
  onRunningChange: (running: boolean) => void;
};

// The run tab (ROADMAP 2.6a). Ask runs show the scripted live view; Check and Compare keep a summary card until
// their scripts exist. Every run here is a demo: nothing was uploaded or sent.
export default function RunTab({ run, runKey, scenario, onBack, onRunningChange }: Props) {
  const t = useTranslations("workspace");
  if (!run) {
    return (
      <section className={styles.peek}>
        <div>
          <b className={styles.peekTitle}>{t("runTab.peekTitle")}</b>
          <p className={styles.peekSub}>{t("runTab.peekSub")}</p>
        </div>
        <Button onClick={onBack}>{t("runTab.goAsk")}</Button>
      </section>
    );
  }
  if (run.mode === "ask") {
    return <RunLive key={runKey} run={run} scenario={scenario} onBack={onBack} onRunningChange={onRunningChange} />;
  }
  return (
    <section className={styles.peek}>
      <div>
        <span className={styles.demoTag}>{t("live.demoTag")}</span>
        <b className={styles.peekTitle}>{t("runTab.readyTitle")}</b>
        <p className={styles.peekSub}>{t("runTab.readyBody")}</p>
        <dl className={styles.summary}>
          <dt>{t("runTab.summaryMode")}</dt>
          <dd>{t(`modes.${run.mode}`)}</dd>
          <dt>{t("steps.askFiles").replace(/^\d+\.\s*/, "")}</dt>
          <dd>{t("runTab.summaryFiles", { count: run.fileCount })}</dd>
          {run.question ? (
            <>
              <dt>{t("runTab.summaryQuestion")}</dt>
              <dd className={styles.question}>{run.question}</dd>
            </>
          ) : null}
        </dl>
      </div>
      <Button onClick={onBack}>{t("runTab.change")}</Button>
    </section>
  );
}
