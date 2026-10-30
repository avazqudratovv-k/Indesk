"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { DEMO_LIMITS } from "@/lib/limits";
import { planKey } from "@/lib/my/display";
import { loadUsage, type Usage } from "@/lib/usage/api";
import styles from "./my.module.css";

export type UsageState = { status: "loading" } | { status: "error" } | { status: "ready"; usage: Usage };

// What the card shows for one state. Free runs are 3 in total, not per month: "{left} of {total} free runs left". A plan
// whose /usage answer has no counts shows the plan name and no number.
export function UsageCardView({ state, onRetry }: { state: UsageState; onRetry: () => void }) {
  const t = useTranslations("my");
  const tCommon = useTranslations("common");
  const percent = state.status === "ready" && state.usage.free && state.usage.free.total > 0 ? (state.usage.free.left / state.usage.free.total) * 100 : 0;

  return (
    <section className={styles.card} aria-labelledby="my-usage-title" aria-busy={state.status === "loading"}>
      <h2 id="my-usage-title" className={styles.cardTitle}>
        {t("usage.title")}
      </h2>

      {state.status === "loading" ? (
        <p className={styles.state} role="status">
          {tCommon("loading")}
        </p>
      ) : state.status === "error" ? (
        <div className={styles.errorCard} role="alert">
          <p>{t("loadError")}</p>
          <Button size="sm" onClick={onRetry}>
            {t("retry")}
          </Button>
        </div>
      ) : state.usage.free ? (
        <>
          <p className={styles.usageText}>{t("usage.left", { left: state.usage.free.left, total: state.usage.free.total })}</p>
          <div className={styles.bar} role="progressbar" aria-label={t("usage.barLabel")} aria-valuemin={0} aria-valuemax={state.usage.free.total} aria-valuenow={state.usage.free.left}>
            <div className={styles.barFill} style={{ width: `${percent}%` }} />
          </div>
          {state.usage.free.left === 0 ? <p className={styles.help}>{t("usage.none")}</p> : null}
        </>
      ) : (
        <p className={styles.usageText}>{t(`plan.${planKey(state.usage.plan)}`)}</p>
      )}

      <p className={styles.help}>{t("usage.limits", { mb: DEMO_LIMITS.max_file_mb, rows: DEMO_LIMITS.csv_rows, pages: DEMO_LIMITS.pdf_pages, runs: DEMO_LIMITS.runs_per_day })}</p>
    </section>
  );
}

export default function UsageCard() {
  const [state, setState] = useState<UsageState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  // loadUsage never throws: null means the request failed or the body was not the expected shape.
  useEffect(() => {
    const controller = new AbortController();
    loadUsage(controller.signal).then((usage) => {
      if (!controller.signal.aborted) setState(usage ? { status: "ready", usage } : { status: "error" });
    });
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  return <UsageCardView state={state} onRetry={retry} />;
}
