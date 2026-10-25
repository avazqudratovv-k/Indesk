"use client";

import { useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/use-session";
import { quoteCustomPlan } from "@/lib/plans/calc";
import type { CustomPlanOffer, PlanOffer } from "@/lib/types";
import Check from "./Check";
import Checkout from "./Checkout";
import CustomCalculator, { type CustomChoices } from "./CustomCalculator";
import CustomSummary from "./CustomSummary";
import EnforceCard from "./EnforceCard";
import PlanCard from "./PlanCard";
import UsagePanel, { type DemoPlan } from "./UsagePanel";
import { usePlanMoney } from "./use-plan-money";
import styles from "./PlansView.module.css";

type Choice = "pro" | "payg" | "custom";

const defaultChoices: CustomChoices = { fileSize: 0, dataTier: 0, retention: 0, parallel: 0 };

// The whole Plans screen. All state here is client-only demo state: nothing is stored, sent or charged.
export default function PlansView({ offers, custom }: { offers: PlanOffer[]; custom: CustomPlanOffer }) {
  const t = useTranslations("plans");
  const session = useSession();
  const { money } = usePlanMoney();
  const free = offers.find((offer) => offer.plan === "free");
  const pro = offers.find((offer) => offer.plan === "pro");
  const payg = offers.find((offer) => offer.plan === "payg");
  if (!free || !pro || !payg) throw new Error("plans mock is missing a plan");

  const paygRuns = payg.runs;
  const signedIn = session.signedIn;
  const [plan, setPlan] = useState<DemoPlan>(session.user?.plan === "pro" ? "pro" : "free");
  const [credits, setCredits] = useState(0);
  const [customLimit, setCustomLimit] = useState(0);
  const [used, setUsed] = useState(1);
  const [choice, setChoice] = useState<Choice | null>(null);
  const [paid, setPaid] = useState(false);
  const [runs, setRuns] = useState(custom.runs.default);
  const [choices, setChoices] = useState<CustomChoices>(defaultChoices);
  const trigger = useRef<HTMLElement | null>(null);
  const paidRef = useRef<HTMLElement>(null);

  const quote = useMemo(() => quoteCustomPlan(runs, custom), [runs, custom]);
  const limit = plan === "custom" ? customLimit : plan === "pro" ? pro.runs : free.runs + credits;
  const shownUsed = Math.min(used, limit);
  const blocked = shownUsed >= limit;

  function open(next: Choice, from: HTMLElement) {
    trigger.current = from;
    setChoice(next);
    setPaid(false);
  }

  function cancel() {
    setChoice(null);
    trigger.current?.focus();
  }

  // Called by the checkout's Done button after a successful demo payment. A declined payment never gets here.
  function applyPlan() {
    if (choice === "custom") {
      setPlan("custom");
      setCustomLimit(quote.runs);
    } else if (choice === "pro") {
      setPlan("pro");
    } else {
      setCredits((value) => value + paygRuns);
    }
    setChoice(null);
    setPaid(true);
    // Focus goes back to the button that opened the checkout. After a Pro purchase that button is disabled
    // ("Current plan"), so the banner at the top takes the focus and is brought into view instead.
    requestAnimationFrame(() => {
      const opener = trigger.current;
      if (opener?.isConnected && !(opener instanceof HTMLButtonElement && opener.disabled)) {
        opener.focus();
        return;
      }
      const banner = paidRef.current;
      if (!banner) return;
      banner.focus({ preventScroll: true });
      const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      banner.scrollIntoView({ block: "center", behavior: calm ? "auto" : "smooth" });
    });
  }

  function reset() {
    setUsed(1);
    setPlan("free");
    setCredits(0);
    setChoice(null);
    setPaid(false);
  }

  const summary =
    choice === "pro"
      ? t("checkout.summaryPro", { price: money(pro.price) })
      : choice === "payg"
        ? t("checkout.summaryPayg", { runs: payg.runs, price: money(payg.price) })
        : t("checkout.summaryCustom", { runs: quote.runs, price: money(quote.total) });

  return (
    <main className={styles.main}>
      <div className={styles.intro}>
        <h1 className={styles.title}>{t("title")}</h1>
        <p className={styles.sub}>{t("sub")}</p>
      </div>

      {paid ? (
        <section ref={paidRef} tabIndex={-1} className={styles.paid} role="status">
          <Check size={18} stroke={3} />
          {t("paidMsg")}
        </section>
      ) : null}

      {blocked ? (
        <section className={styles.limit} role="alert">
          <div className={styles.limitTitle}>{t("limitTitle")}</div>
          <div className={styles.limitBody}>{t("limitBody")}</div>
        </section>
      ) : null}

      <section className={styles.row}>
        {[free, pro, payg].map((offer) => (
          <PlanCard
            key={offer.plan}
            offer={offer}
            signedIn={signedIn}
            current={signedIn && (offer.plan === "free" ? plan === "free" && credits === 0 : offer.plan === "pro" && plan === "pro")}
            onChoose={(from) => open(offer.plan === "pro" ? "pro" : "payg", from)}
          />
        ))}
      </section>

      <section className={styles.row} aria-label={t("custom.title")}>
        <CustomCalculator
          offer={custom}
          quote={quote}
          choices={choices}
          onRuns={setRuns}
          onChoice={(key, index) => setChoices((value) => ({ ...value, [key]: index }))}
        />
        <CustomSummary offer={custom} pro={pro} quote={quote} choices={choices} signedIn={signedIn} onChoose={(from) => open("custom", from)} />
      </section>

      <section className={styles.row}>
        <UsagePanel
          plan={plan}
          hasCredits={credits > 0}
          used={shownUsed}
          limit={limit}
          onSimulate={() => {
            setUsed(shownUsed + 1);
            setPaid(false);
          }}
          onReset={reset}
        />
        <EnforceCard />
      </section>

      {choice ? <Checkout summary={summary} onDone={applyPlan} onCancel={cancel} /> : null}

      <p className={styles.demoLine}>{t("demoNoPayments")}</p>
    </main>
  );
}
