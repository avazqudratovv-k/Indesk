"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";
import Button from "@/components/ui/Button";
import { useSession, useSessionActions } from "@/hooks/use-session";
import { confirmEmail, fetchMe } from "@/lib/auth/api";
import { takeFragmentToken } from "@/lib/auth/recovery";
import { verifyPhase, type VerifyPhase } from "@/lib/auth/verification";
import ResendLink from "./ResendLink";
import styles from "./AuthForm.module.css";

// The token comes from the URL fragment (#token=...). It is read once, removed from the address bar at once, kept only in
// a ref and sent once. A missing token and a bad one look the same. It is never logged or stored.
export default function VerifyEmail() {
  const t = useTranslations("verify.page");
  const session = useSession();
  const { updateUser } = useSessionActions();
  const ids = useId();
  const token = useRef<string | null>(null);
  const started = useRef(false);
  const signedIn = useRef(false);
  const [phase, setPhase] = useState<VerifyPhase>("confirming");

  useEffect(() => {
    signedIn.current = session.signedIn;
  }, [session.signedIn]);

  useEffect(() => {
    // Strict mode runs this twice: the second run must neither lose the token nor confirm twice.
    if (started.current) return;
    started.current = true;
    token.current = takeFragmentToken(window.location, window.history);
    const found = token.current;
    if (!found) {
      setPhase(verifyPhase(false, "pending"));
      return;
    }
    token.current = null;
    confirmEmail(found).then(
      () => {
        setPhase(verifyPhase(true, "ok"));
        // The banner goes away once the session user is verified. Signed out: nothing to refresh.
        if (signedIn.current) fetchMe().then(updateUser, () => {});
      },
      () => setPhase(verifyPhase(true, "invalid")),
    );
  }, [updateUser]);

  const needsResend = session.status === "signedIn" && !session.user.email_verified;
  return (
    <section className={styles.card} aria-labelledby={`${ids}-title`}>
      <div>
        <h1 id={`${ids}-title`} className={styles.title}>
          {t("title")}
        </h1>
      </div>
      <div role="status" aria-live="polite">
        {phase === "confirming" ? <p className={styles.notice}>{t("confirming")}</p> : null}
        {phase === "verified" ? (
          <>
            <p className={styles.notice}>{t("verified")}</p>
            <p className={styles.sub}>{t("verifiedSub")}</p>
          </>
        ) : null}
      </div>
      {phase === "verified" ? (
        <Button href="/workspace" variant="primary">
          {t("toWorkspace")}
        </Button>
      ) : null}
      {phase === "invalid" ? (
        <>
          <p className={styles.formError} role="alert">
            {t("invalid")}
          </p>
          {session.signedIn ? needsResend ? <ResendLink /> : null : session.status === "signedOut" ? (
            <Link href="/login" className={styles.switchLink}>
              {t("logIn")}
            </Link>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
