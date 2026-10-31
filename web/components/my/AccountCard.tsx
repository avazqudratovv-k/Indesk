"use client";

import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { useLogout } from "@/hooks/use-logout";
import styles from "./my.module.css";

// Log out and one honest line about retention. No settings toggles (no PATCH /me yet) and no Delete account (after the deploy).
export default function AccountCard() {
  const t = useTranslations("my.account");
  const tNav = useTranslations("nav");
  const { state, logout } = useLogout();

  return (
    <section className={styles.card} aria-labelledby="my-account-title">
      <h2 id="my-account-title" className={styles.cardTitle}>
        {t("title")}
      </h2>
      <p className={styles.help}>{t("retention")}</p>
      <div className={styles.cardActions}>
        <Button onClick={logout} disabled={state === "busy"} aria-live="polite">
          {state === "busy" ? tNav("logoutBusy") : tNav("logout")}
        </Button>
      </div>
      {state === "failed" ? (
        <p className={styles.rowError} role="alert">
          {tNav("logoutFailed")}
        </p>
      ) : null}
    </section>
  );
}
