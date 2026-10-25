import { forwardRef } from "react";
import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { exampleReportHref } from "@/components/home/agents";
import type { RunScenario } from "@/lib/run/mock-run";
import styles from "./RunHeader.module.css";

type Props = {
  title: string;
  finished: boolean;
  scenario: RunScenario;
  onBack: () => void;
  onReplay: () => void;
};

// Board header: "Question" eyebrow, the question as h1, then Change question / Replay run / View report (only when the run finished).
// Failed runs have no report, so the link is not offered there. The h1 takes focus when a run starts.
const RunHeader = forwardRef<HTMLHeadingElement, Props>(function RunHeader({ title, finished, scenario, onBack, onReplay }, ref) {
  const t = useTranslations("workspace");
  return (
    <div className={styles.head}>
      <div className={styles.text}>
        <div className={styles.eyebrow}>{t("live.question")}</div>
        <h1 ref={ref} tabIndex={-1} className={styles.title}>
          {title}
        </h1>
        {finished ? <span className={`${styles.mark} ${scenario === "answered" ? "" : scenario === "partial" ? styles.warn : styles.bad}`}>{t(`live.mark.${scenario}`)}</span> : null}
      </div>
      <div className={styles.actions}>
        <Button size="sm" onClick={onBack}>
          {t("runTab.change")}
        </Button>
        <Button size="sm" onClick={onReplay} disabled={!finished}>
          {t("live.replay")}
        </Button>
        {finished && scenario !== "failed" ? (
          <Button size="sm" variant="ink" href={exampleReportHref.ask}>
            {t("live.viewReport")}
          </Button>
        ) : null}
      </div>
    </div>
  );
});

export default RunHeader;
