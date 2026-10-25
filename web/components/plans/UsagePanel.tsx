"use client";

import { useTranslations } from "next-intl";
import styles from "./UsagePanel.module.css";

export type DemoPlan = "free" | "pro" | "custom";

type UsagePanelProps = {
  plan: DemoPlan;
  hasCredits: boolean;
  used: number;
  limit: number;
  onSimulate: () => void;
  onReset: () => void;
};

// Client-only demo counter: nothing is stored or sent, and it enforces nothing.
export default function UsagePanel({ plan, hasCredits, used, limit, onSimulate, onReset }: UsagePanelProps) {
  const t = useTranslations("plans.usage");
  const demoBadge = useTranslations("plans")("demoBadge");
  const blocked = used >= limit;
  const planName = plan === "custom" ? t("planCustom") : plan === "pro" ? t("planPro") : hasCredits ? t("planFreeCredits") : t("planFree");
  const text = t("text", { used, limit });
  const percent = Math.round((used / limit) * 100);
  return (
    <section className={styles.card} aria-labelledby="plans-usage">
      <div className={styles.head}>
        <h2 id="plans-usage" className={styles.title}>
          {t("title")}
        </h2>
        <span className={styles.chips}>
          <span className={styles.demo}>{demoBadge}</span>
          <span className={styles.plan}>{planName}</span>
        </span>
      </div>
      <div className={styles.text}>{text}</div>
      <div className={styles.track} role="img" aria-label={text}>
        <div className={`${styles.fill} ${blocked ? styles.fillFull : ""}`} style={{ width: `${percent}%` }} />
      </div>
      <div className={styles.actions}>
        <button type="button" className={styles.run} disabled={blocked} onClick={onSimulate}>
          {t("simulate")}
        </button>
        <button type="button" className={styles.reset} onClick={onReset}>
          {t("reset")}
        </button>
      </div>
      <p className={styles.note}>{t("demoNote")}</p>
    </section>
  );
}
