"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { barWidth, percent, photoPercent, type ChartView } from "@/lib/report/view";
import ScrollRegion from "./ScrollRegion";
import styles from "./GrowthChart.module.css";

// The chart is drawn from the numbers in the evidence payload (never by a model). A bar is the computed value; the black
// tick is what the chart photo showed. "View as table" swaps the bars for the same numbers in a table (board behaviour).
export default function GrowthChart({ chart }: { chart: ChartView }) {
  const t = useTranslations("report.simple");
  const [table, setTable] = useState(false);
  const hasPhoto = chart.bars.some((bar) => bar.photo !== null);
  return (
    <section className={styles.card} aria-labelledby="report-chart">
      <div className={styles.head}>
        <h2 id="report-chart" className={styles.title}>
          {chart.title}
        </h2>
        <button type="button" className={styles.toggle} aria-pressed={table} onClick={() => setTable((value) => !value)}>
          {t("viewTable")}
        </button>
      </div>
      <div className={styles.key}>
        <span className={styles.keyItem}>
          <span className={styles.keyBar} aria-hidden="true" />
          {t("keyBar")}
        </span>
        {hasPhoto ? (
          <span className={styles.keyItem}>
            <span className={styles.keyTick} aria-hidden="true" />
            {t("keyTick")}
          </span>
        ) : null}
      </div>
      {table ? (
        <ScrollRegion label={t("chartLabel")} className={styles.scroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">{t("thStation")}</th>
                <th scope="col">{t("thData")}</th>
                {hasPhoto ? <th scope="col">{t("thChart")}</th> : null}
              </tr>
            </thead>
            <tbody>
              {chart.bars.map((bar) => (
                <tr key={bar.label}>
                  <td>{bar.label}</td>
                  <td className={styles.num}>{percent(bar.value)}</td>
                  {hasPhoto ? <td className={styles.num}>{bar.photo === null ? "–" : photoPercent(bar.photo)}</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      ) : (
        <ul className={styles.bars} aria-label={t("chartLabel")}>
          {chart.bars.map((bar) => (
            <li
              key={bar.label}
              className={styles.bar}
              title={bar.photo === null ? undefined : t("tip", { name: bar.label, data: percent(bar.value), photo: photoPercent(bar.photo) })}
            >
              <span className={styles.name}>{bar.label}</span>
              <span className={styles.track} aria-hidden="true">
                <span className={styles.fill} style={{ width: barWidth(bar.value, chart.max) }} />
                {bar.photo === null ? null : <span className={styles.tick} style={{ left: barWidth(bar.photo, chart.max) }} />}
              </span>
              <span className={styles.value}>{percent(bar.value)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
