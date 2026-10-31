"use client";

import { useFormatter, useTranslations } from "next-intl";
import Eyebrow from "@/components/ui/Eyebrow";
import type { CustomQuote } from "@/lib/plans/calc";
import type { CustomPlanOffer } from "@/lib/types";
import { usePlanMoney } from "./use-plan-money";
import styles from "./CustomCalculator.module.css";

type CustomCalculatorProps = {
  offer: CustomPlanOffer;
  quote: CustomQuote;
  onRuns: (runs: number) => void;
};

const scaleStops = [10, 250, 500, 1000];

// Left card of the custom plan: the runs slider. Only runs set the price; the demo has one set of file limits for everyone.
export default function CustomCalculator({ offer, quote, onRuns }: CustomCalculatorProps) {
  const t = useTranslations("plans.custom");
  const format = useFormatter();
  const { money } = usePlanMoney();

  return (
    <div className={styles.card}>
      <div className={styles.intro}>
        <Eyebrow>{t("eyebrow")}</Eyebrow>
        <h2 className={styles.title}>{t("title")}</h2>
        <p className={styles.sub}>{t("sub", { minimum: money(offer.minimum) })}</p>
      </div>
      <div className={styles.runs}>
        <div className={styles.runsHead}>
          <label htmlFor="custom-runs" className={styles.runsLabel}>
            {t("runsLabel")}
          </label>
          <output htmlFor="custom-runs" className={styles.runsValue}>
            {format.number(quote.runs)}
          </output>
        </div>
        <input
          id="custom-runs"
          type="range"
          className={styles.range}
          min={offer.runs.min}
          max={offer.runs.max}
          step={offer.runs.step}
          value={quote.runs}
          aria-valuetext={t("runsValueText", { runs: quote.runs, price: money(quote.total) })}
          onChange={(event) => onRuns(Number(event.target.value))}
        />
        <div className={styles.scale} aria-hidden="true">
          {scaleStops.map((stop) => (
            <span key={stop}>{format.number(stop)}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
