"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useId, useRef, useState, type FormEvent } from "react";
import { ApiError, apiErrorKey, retryMinutes } from "@/lib/api/errors";
import { forgotPassword } from "@/lib/auth/api";
import { mailLang, validateForgot, type RecoveryErrorKey } from "@/lib/auth/recovery";
import styles from "./AuthForm.module.css";

type Status = "idle" | "submitting" | "sent";

// One email field. Every 202 shows the same line: it never says whether the account exists or an email was delivered.
export default function ForgotForm() {
  const t = useTranslations("recovery");
  const tAuth = useTranslations("auth");
  const tApi = useTranslations("apiErrors");
  const locale = useLocale();
  const ids = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<RecoveryErrorKey | null>(null);
  const [serverError, setServerError] = useState<ApiError | null>(null);
  const [status, setStatus] = useState<Status>("idle");

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (status !== "idle") return;
    const found = validateForgot(email);
    setFieldError(found);
    if (found) {
      emailRef.current?.focus();
      return;
    }
    setServerError(null);
    setStatus("submitting");
    try {
      await forgotPassword({ email: email.trim(), lang: mailLang(locale) });
      setStatus("sent");
    } catch (caught) {
      setServerError(caught instanceof ApiError ? caught : new ApiError(0, "UNKNOWN"));
      setStatus("idle");
    }
  }

  const busy = status === "submitting";
  const sent = status === "sent";
  return (
    <section className={styles.card} aria-labelledby={`${ids}-title`}>
      <div>
        <h1 id={`${ids}-title`} className={styles.title}>
          {t("forgot.title")}
        </h1>
        <p className={styles.sub}>{t("forgot.sub")}</p>
      </div>
      {sent ? (
        <p className={styles.notice} role="status">
          {t("forgot.sent")}
        </p>
      ) : (
        <form className={styles.form} method="post" onSubmit={onSubmit} noValidate aria-busy={busy}>
          <div className={styles.field}>
            <label htmlFor={`${ids}-email`} className={styles.label}>
              {tAuth("email")}
            </label>
            <input
              ref={emailRef}
              id={`${ids}-email`}
              name="email"
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder={tAuth("emailPlaceholder")}
              value={email}
              onChange={(event) => {
                setEmail(event.target.value);
                setFieldError(null);
                setServerError(null);
              }}
              className={styles.input}
              aria-invalid={fieldError ? true : undefined}
              aria-describedby={fieldError ? `${ids}-email-error` : undefined}
            />
            <p id={`${ids}-email-error`} className={styles.error} aria-live="polite">
              {fieldError ? tAuth(`errors.${fieldError as "emailRequired"}`) : null}
            </p>
          </div>
          <button type="submit" className={styles.cta} disabled={busy}>
            {busy ? t("forgot.submitting") : t("forgot.cta")}
          </button>
          <p className={styles.formError} role="alert">
            {serverError ? tApi(apiErrorKey(serverError), { minutes: retryMinutes(serverError) }) : null}
          </p>
        </form>
      )}
      <p className={styles.switch}>
        <Link href="/login" className={styles.switchLink}>
          {t("backToLogin")}
        </Link>
      </p>
    </section>
  );
}
