"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { type CardErrors, formatCardNumber, formatCvc, formatExpiry, isDeclinedCard, validateCard } from "@/lib/plans/card";
import CardField from "./CardField";
import ResultIcon from "./ResultIcon";
import styles from "./Checkout.module.css";

type CheckoutProps = {
  summary: string;
  // Success only: the parent applies the plan and closes the window.
  onDone: () => void;
  onCancel: () => void;
};

type View = "form" | "processing" | "success" | "declined";

const PROCESSING_MS = 1200;

// Fake checkout. Card values live only in this component's state: never logged, stored, put in a URL or sent anywhere.
// The outcome is a local rule: 4000 0000 0000 0002 is declined, any other complete number succeeds.
export default function Checkout({ summary, onDone, onCancel }: CheckoutProps) {
  const t = useTranslations("plans");
  const headingRef = useRef<HTMLHeadingElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const [view, setView] = useState<View>("form");
  const [number, setNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvc, setCvc] = useState("");
  const [errors, setErrors] = useState<CardErrors>({});

  // The section opens far below the button on phones, and every new view needs the screen reader to land on its title.
  useEffect(() => {
    if (view === "processing") return;
    const heading = headingRef.current;
    if (!heading) return;
    heading.focus({ preventScroll: true });
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    heading.scrollIntoView({ block: "center", behavior: calm ? "auto" : "smooth" });
  }, [view]);

  // Closing in any way must drop the card values and the pending result.
  useEffect(() => () => window.clearTimeout(timer.current), []);

  function clearCard() {
    setNumber("");
    setExpiry("");
    setCvc("");
    setErrors({});
  }

  function pay() {
    const found = validateCard({ number, expiry, cvc }, new Date());
    setErrors(found);
    if (Object.keys(found).length > 0) {
      const first = found.number ? "plans-card-number" : found.expiry ? "plans-card-exp" : "plans-card-cvc";
      document.getElementById(first)?.focus();
      return;
    }
    const declined = isDeclinedCard(number);
    setView("processing");
    timer.current = window.setTimeout(() => {
      // A decline keeps the values for "Try again"; a success has no further use for them.
      if (!declined) clearCard();
      setView(declined ? "declined" : "success");
    }, PROCESSING_MS);
  }

  function done() {
    clearCard();
    onDone();
  }

  function cancel() {
    clearCard();
    onCancel();
  }

  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key !== "Escape" || view === "processing") return;
    event.preventDefault();
    if (view === "success") done();
    else cancel();
  }

  const message = (key: "numberIncomplete" | "expiryInvalid" | "expiryPast" | "cvcShort" | undefined) =>
    key ? t(`checkout.errors.${key}`) : undefined;

  if (view === "success" || view === "declined") {
    const ok = view === "success";
    return (
      <section
        className={`${styles.card} ${styles.resultCard} ${ok ? "" : styles.shake}`}
        aria-labelledby="plans-checkout"
        onKeyDown={onKeyDown}
      >
        <div className={styles.result} role={ok ? "status" : "alert"}>
          <ResultIcon kind={ok ? "success" : "declined"} />
          <h2 id="plans-checkout" ref={headingRef} tabIndex={-1} className={styles.title}>
            {t(ok ? "checkout.successTitle" : "checkout.declinedTitle")}
          </h2>
          {ok ? <div className={styles.summary}>{summary}</div> : null}
          <p className={styles.resultLine}>{t(ok ? "checkout.successLine" : "checkout.declinedLine")}</p>
          <div className={styles.actions}>
            {ok ? (
              <button type="button" className={styles.pay} onClick={done}>
                {t("checkout.done")}
              </button>
            ) : (
              <>
                <button type="button" className={styles.pay} onClick={() => setView("form")}>
                  {t("checkout.tryAgain")}
                </button>
                <button type="button" className={styles.cancel} onClick={cancel}>
                  {t("checkout.cancel")}
                </button>
              </>
            )}
          </div>
        </div>
      </section>
    );
  }

  const busy = view === "processing";
  return (
    <section className={styles.card} aria-labelledby="plans-checkout" onKeyDown={onKeyDown}>
      <div className={styles.info}>
        <h2 id="plans-checkout" ref={headingRef} tabIndex={-1} className={styles.title}>
          {t("checkout.title")}
        </h2>
        <div className={styles.summary}>{summary}</div>
        <p className={styles.testNote}>{t("checkout.testNote")}</p>
        <p className={styles.testNote}>{t("checkout.demoHint")}</p>
        <p className={styles.noPayments}>{t("demoNoPayments")}</p>
        <p className={styles.noPayments}>{t("checkout.noRealCards")}</p>
      </div>
      {/* preventDefault: a native submit must never run. The inputs have no name either, so no value could reach a URL. */}
      <form
        className={styles.fields}
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy) pay();
        }}
      >
        <CardField
          id="plans-card-number"
          label={t("checkout.cardLabel")}
          value={number}
          placeholder={t("checkout.cardPlaceholder")}
          error={message(errors.number)}
          locked={busy}
          format={formatCardNumber}
          onValue={setNumber}
        />
        <div className={styles.pair}>
          <CardField
            id="plans-card-exp"
            label={t("checkout.expLabel")}
            value={expiry}
            placeholder={t("checkout.expPlaceholder")}
            error={message(errors.expiry)}
            locked={busy}
            format={formatExpiry}
            onValue={setExpiry}
          />
          <CardField
            id="plans-card-cvc"
            label={t("checkout.cvcLabel")}
            value={cvc}
            placeholder={t("checkout.cvcPlaceholder")}
            error={message(errors.cvc)}
            locked={busy}
            format={formatCvc}
            onValue={setCvc}
          />
        </div>
        <p className={styles.processing} role="status">
          {busy ? t("checkout.processing") : ""}
        </p>
        <div className={styles.actions}>
          <button type="submit" className={styles.pay} disabled={busy}>
            {busy ? t("checkout.processing") : t("checkout.payBtn")}
          </button>
          <button type="button" className={styles.cancel} disabled={busy} onClick={cancel}>
            {t("checkout.cancel")}
          </button>
        </div>
      </form>
    </section>
  );
}
