"use client";

import { useFormatter, useTranslations } from "next-intl";
import Eyebrow from "@/components/ui/Eyebrow";
import type { CustomQuote } from "@/lib/plans/calc";
import type { CustomPlanOffer } from "@/lib/types";
import ChoiceGroup from "./ChoiceGroup";
import { usePlanMoney } from "./use-plan-money";
import styles from "./CustomCalculator.module.css";

// Indexes into the offer's option lists. The options carry no price (DECISIONS #18 prices only runs).
export type CustomChoices = { fileSize: number; dataTier: number; retention: number; parallel: number };

type CustomCalculatorProps = {
  offer: CustomPlanOffer;
  quote: CustomQuote;
  choices: CustomChoices;
  onRuns: (runs: number) => void;
  onChoice: (key: keyof CustomChoices, index: number) => void;
};

const scaleStops = [10, 250, 500, 1000];

// Left card of the custom plan: the runs slider and the four option groups.
export default function CustomCalculator({ offer, quote, choices, onRuns, onChoice }: CustomCalculatorProps) {
  const t = useTranslations("plans.custom");
  const format = useFormatter();
  const { money } = usePlanMoney();
  const dataLabel = (tier: string) => (tier === offer.data_tier[0] ? t("dataStandard") : t("dataLarge"));
  const groups = [
    { key: "fileSize", title: t("fileSize.title"), hint: t("fileSize.hint"), labels: offer.max_file_mb.map((mb) => t("mb", { mb })) },
    { key: "dataTier", title: t("dataSize.title"), hint: t("dataSize.hint"), labels: offer.data_tier.map(dataLabel) },
    { key: "parallel", title: t("parallel.title"), hint: t("parallel.hint"), labels: offer.parallel.map((count) => t("count", { count })) },
  ] as const;

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
      {groups.map((group) => (
        <ChoiceGroup
          key={group.key}
          title={group.title}
          hint={group.hint}
          choices={group.labels.map((label, index) => ({ value: String(index), label }))}
          selected={String(choices[group.key])}
          onPick={(value) => onChoice(group.key, Number(value))}
        />
      ))}
      <p className={styles.note}>{t("optionsNote")}</p>
    </div>
  );
}
