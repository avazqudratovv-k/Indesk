"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import type { DemoLimits, PlanOffer } from "@/lib/types";
import Check from "./Check";
import { usePlanMoney } from "./use-plan-money";
import styles from "./PlanCard.module.css";

type PlanCardProps = {
  offer: PlanOffer;
  // Set on the Free card only: the demo's real limits. Paid cards list runs and price and nothing else.
  limits?: DemoLimits;
  signedIn: boolean;
  current: boolean;
  onChoose: (trigger: HTMLElement) => void;
};

const runsKey = { free: "features.runsFree", pro: "features.runsPro", payg: "features.runsPayg" } as const;

// One of the three plan cards. Free is never bought; Pro and Pay as you go open the demo checkout (visitors go to Log in first).
export default function PlanCard({ offer, limits, signedIn, current, onChoose }: PlanCardProps) {
  const t = useTranslations("plans");
  const format = useFormatter();
  const { money } = usePlanMoney();
  const { plan } = offer;
  const features = [
    t(runsKey[plan], { runs: offer.runs }),
    ...(limits
      ? [
          t("features.fileSize", { mb: limits.max_file_mb }),
          t("features.csvRows", { rows: limits.csv_rows }),
          t("features.pdfPages", { pages: limits.pdf_pages }),
        ]
      : []),
  ];
  const label = current ? t("currentPlan") : t(`cta.${plan}`, { runs: format.number(offer.runs) });
  const headingId = `plan-${plan}`;
  const cardClass = [styles.card, current ? styles.cardOn : offer.popular ? styles.cardPopular : ""].filter(Boolean).join(" ");

  let action: React.ReactNode;
  if (plan === "free") {
    action = signedIn ? (
      <button type="button" className={`${styles.btn} ${styles.btnQuiet}`} disabled>
        {label}
      </button>
    ) : (
      <Link href="/signup" className={`${styles.btn} ${styles.btnSoft} ${styles.btnLink}`}>
        {t("startFree")}
      </Link>
    );
  } else if (!signedIn) {
    action = (
      <Link href="/login" className={`${styles.btn} ${plan === "pro" ? styles.btnAccent : styles.btnInk} ${styles.btnLink}`}>
        {label}
      </Link>
    );
  } else {
    action = (
      <button
        type="button"
        className={`${styles.btn} ${current ? styles.btnQuiet : plan === "pro" ? styles.btnAccent : styles.btnInk}`}
        disabled={current}
        onClick={(event) => onChoose(event.currentTarget)}
      >
        {label}
      </button>
    );
  }

  return (
    <article className={cardClass} aria-labelledby={headingId}>
      <div className={styles.head}>
        <h2 id={headingId} className={styles.name}>
          {t(`names.${plan}`)}
        </h2>
        {offer.popular ? <span className={styles.popular}>{t("popular")}</span> : null}
      </div>
      <p className={styles.priceRow}>
        <span className={styles.price}>{money(offer.price)}</span>
        <span className={styles.per}>{t(`per.${offer.period}`, { runs: offer.runs })}</span>
      </p>
      <ul className={styles.features}>
        {features.map((text) => (
          <li key={text} className={styles.feature}>
            <span className={styles.tick}>
              <Check size={11} stroke={4} />
            </span>
            {text}
          </li>
        ))}
      </ul>
      {action}
    </article>
  );
}
