import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import type { RunAgent } from "@/lib/run/mock-run";
import styles from "./FailureBar.module.css";

// Error state of the run: a failed agent is named, never hidden, and can be retried. In this demo Retry replays the
// scripted example as a success; no model is called.
export default function FailureBar({ agent, onRetry }: { agent: RunAgent; onRetry: () => void }) {
  const t = useTranslations("workspace");
  const home = useTranslations("home.team");
  const name = home(`${agent}.name`);
  return (
    <div className={styles.bar} role="alert">
      <div className={styles.text}>
        <b>{t("live.failure.title", { agent: name })}</b>
        <span>{t("live.failure.body")}</span>
        <span className={styles.note}>{t("live.failure.note")}</span>
      </div>
      <Button onClick={onRetry}>{t("live.failure.retry", { agent: name })}</Button>
    </div>
  );
}
