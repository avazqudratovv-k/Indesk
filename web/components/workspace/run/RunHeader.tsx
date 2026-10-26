import { forwardRef } from "react";
import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { reportHrefFor, type RunScenario } from "@/lib/run/mock-run";
import styles from "./RunHeader.module.css";

// `real` is set for a real run: the mark is chosen by the page, there is no Replay, and there is no report link
// (the report screen is built in 4.4).
type Real = { mark: { tone: "ok" | "warn" | "bad"; text: string } | null };

type Props = {
  title: string;
  finished: boolean;
  scenario?: RunScenario;
  onBack: () => void;
  onReplay?: () => void;
  real?: Real;
};

// Board header: "Question" eyebrow, the question as h1, then Change question / Replay run / View report (only when the run finished).
// Failed runs have no report, so the link is not offered there. The h1 takes focus when a run starts.
const RunHeader = forwardRef<HTMLHeadingElement, Props>(function RunHeader({ title, finished, scenario = "answered", onBack, onReplay, real }, ref) {
  const t = useTranslations("workspace");
  const reportHref = real ? null : reportHrefFor(scenario);
  return (
    <div className={styles.head}>
      <div className={styles.text}>
        <div className={styles.eyebrow}>{t("live.question")}</div>
        <h1 ref={ref} tabIndex={-1} className={styles.title}>
          {title}
        </h1>
        {real ? (
          real.mark ? <span className={`${styles.mark} ${real.mark.tone === "ok" ? "" : real.mark.tone === "warn" ? styles.warn : styles.bad}`}>{real.mark.text}</span> : null
        ) : finished ? (
          <span className={`${styles.mark} ${scenario === "answered" ? "" : scenario === "partial" ? styles.warn : styles.bad}`}>{t(`live.mark.${scenario}`)}</span>
        ) : null}
      </div>
      <div className={styles.actions}>
        <Button size="sm" onClick={onBack}>
          {t("runTab.change")}
        </Button>
        {onReplay ? (
          <Button size="sm" onClick={onReplay} disabled={!finished}>
            {t("live.replay")}
          </Button>
        ) : null}
        {finished && reportHref ? (
          <Button size="sm" variant="ink" href={reportHref}>
            {t("live.viewReport")}
          </Button>
        ) : null}
      </div>
    </div>
  );
});

export default RunHeader;
