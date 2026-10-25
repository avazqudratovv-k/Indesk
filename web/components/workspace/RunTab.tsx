"use client";

import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import type { RunSummary } from "./AskPanel";
import styles from "./RunTab.module.css";

// Placeholder for the run tab (ROADMAP 2.6 builds the real one). Shows the board's "No run yet" card, or a short
// summary after Run was pressed. Nothing was uploaded or sent.
export default function RunTab({ run, onBack }: { run: RunSummary | null; onBack: () => void }) {
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
  return (
    <section className={styles.peek}>
      <div>
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
