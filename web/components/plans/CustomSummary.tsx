"use client";

import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import type { CustomQuote } from "@/lib/plans/calc";
import type { PlanOffer } from "@/lib/types";
import { usePlanMoney } from "./use-plan-money";
import styles from "./CustomSummary.module.css";

type CustomSummaryProps = {
  pro: PlanOffer;
  quote: CustomQuote;
  signedIn: boolean;
  onChoose: (trigger: HTMLElement) => void;
};

// Right card of the custom plan: always-dark panel with the live price, the breakdown and the checkout button.
export default function CustomSummary({ pro, quote, signedIn, onChoose }: CustomSummaryProps) {
  const t = useTranslations("plans.custom");
  const { money } = usePlanMoney();
  const total = money(quote.total);
  const lines = [
    { label: t("lineRuns", { runs: quote.runs, perRun: money(quote.perRun) }), amount: money(quote.base) },
  ];

  return (
    <div className={`dk ${styles.panel}`}>
      <div className={styles.top}>
        <span className={styles.eyebrow}>{t("yourPlan")}</span>
        <div className={styles.priceRow}>
          <span className={styles.price} style={{ "--chars": total.length } as React.CSSProperties} aria-live="polite">
            {total}
          </span>
          <span className={styles.per}>{t("per")}</span>
        </div>
        <div className={styles.avg}>{t("perRun", { price: money(quote.averagePerRun) })}</div>
        <ul className={styles.lines}>
          {lines.map((line) => (
            <li key={line.label} className={styles.line}>
              <span className={styles.lineLabel}>{line.label}</span>
              <span className={styles.lineAmount}>{line.amount}</span>
            </li>
          ))}
        </ul>
        {quote.isMinimum ? <div className={styles.minNote}>{t("minNote", { minimum: money(quote.minimum), proRuns: pro.runs })}</div> : null}
      </div>
      <div className={styles.bottom}>
        {signedIn ? (
          <Button variant="primary" size="lg" onClick={(event) => onChoose(event.currentTarget)}>
            {t("cta")}
          </Button>
        ) : (
          <Button variant="primary" size="lg" href="/login">
            {t("cta")}
          </Button>
        )}
        <div className={styles.note}>{t("note")}</div>
      </div>
    </div>
  );
}
