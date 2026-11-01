"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { ApiError, apiErrorKey, retryMinutes } from "@/lib/api/errors";
import { resetPassword } from "@/lib/auth/api";
import { postNotice } from "@/lib/auth/notice";
import { takeResetToken, validateReset, type RecoveryErrorKey, type ResetErrors } from "@/lib/auth/recovery";
import styles from "./AuthForm.module.css";

type Phase = "reading" | "ready" | "invalid";

// The token comes from the URL fragment (#token=...). It is read once after mount, removed from the address bar at once,
// and kept only in a ref. It is never put in state, storage, a log or a request URL.
export default function ResetForm() {
  const t = useTranslations("recovery");
  const tAuth = useTranslations("auth");
  const tApi = useTranslations("apiErrors");
  const router = useRouter();
  const ids = useId();
  const token = useRef<string | null>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const confirmRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>("reading");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<ResetErrors>({});
  const [serverError, setServerError] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Strict mode runs this twice: the second run must not lose the token the first one already took.
    token.current ??= takeResetToken(window.location, window.history);
    setPhase(token.current ? "ready" : "invalid");
  }, []);

  function errorText(key: RecoveryErrorKey): string {
    return key === "confirmRequired" || key === "confirmMismatch" ? t(`errors.${key}`) : tAuth(`errors.${key}`);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !token.current) return;
    const found = validateReset(password, confirm);
    setErrors(found);
    if (found.password || found.confirm) {
      (found.password ? passwordRef : confirmRef).current?.focus();
      return;
    }
    setServerError(null);
    setBusy(true);
    try {
      await resetPassword({ token: token.current, newPassword: password });
      token.current = null;
      setPassword("");
      setConfirm("");
      postNotice({ kind: "passwordChanged" });
      router.replace("/login");
    } catch (caught) {
      const error = caught instanceof ApiError ? caught : new ApiError(0, "UNKNOWN");
      setBusy(false);
      if (error.code === "RESET_TOKEN_INVALID") {
        token.current = null;
        setPhase("invalid");
      } else setServerError(error);
    }
  }

  const header = (
    <div>
      <h1 id={`${ids}-title`} className={styles.title}>
        {t("reset.title")}
      </h1>
      {phase === "ready" ? <p className={styles.sub}>{t("reset.sub")}</p> : null}
    </div>
  );

  return (
    <section className={styles.card} aria-labelledby={`${ids}-title`}>
      {header}
      {phase === "invalid" ? (
        <>
          <p className={styles.formError} role="alert">
            {t("reset.invalid")}
          </p>
          <Link href="/forgot-password" className={styles.cta}>
            {t("reset.requestNew")}
          </Link>
        </>
      ) : null}
      {phase === "ready" ? (
        <form className={styles.form} method="post" onSubmit={onSubmit} noValidate aria-busy={busy}>
          <div className={styles.field}>
            <div className={styles.labelRow}>
              <label htmlFor={`${ids}-password`} className={styles.label}>
                {t("reset.newPassword")}
              </label>
              <button type="button" className={styles.toggle} onClick={() => setShowPassword((c) => !c)} aria-pressed={showPassword} aria-controls={`${ids}-password ${ids}-confirm`}>
                {showPassword ? tAuth("hide") : tAuth("show")}
              </button>
            </div>
            <input
              ref={passwordRef}
              id={`${ids}-password`}
              name="new-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder={tAuth("passwordPlaceholder")}
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setErrors((current) => ({ ...current, password: undefined }));
                setServerError(null);
              }}
              className={styles.input}
              aria-invalid={errors.password ? true : undefined}
              aria-describedby={[errors.password ? `${ids}-password-error` : "", `${ids}-hint`].filter(Boolean).join(" ")}
            />
            <span id={`${ids}-hint`} className={styles.hint}>
              {tAuth("passwordHint")}
            </span>
            <p id={`${ids}-password-error`} className={styles.error} aria-live="polite">
              {errors.password ? errorText(errors.password) : null}
            </p>
          </div>
          <div className={styles.field}>
            <label htmlFor={`${ids}-confirm`} className={styles.label}>
              {t("reset.confirm")}
            </label>
            <input
              ref={confirmRef}
              id={`${ids}-confirm`}
              name="confirm-password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              placeholder={tAuth("passwordPlaceholder")}
              value={confirm}
              onChange={(event) => {
                setConfirm(event.target.value);
                setErrors((current) => ({ ...current, confirm: undefined }));
                setServerError(null);
              }}
              className={styles.input}
              aria-invalid={errors.confirm ? true : undefined}
              aria-describedby={errors.confirm ? `${ids}-confirm-error` : undefined}
            />
            <p id={`${ids}-confirm-error`} className={styles.error} aria-live="polite">
              {errors.confirm ? errorText(errors.confirm) : null}
            </p>
          </div>
          <button type="submit" className={styles.cta} disabled={busy}>
            {busy ? t("reset.submitting") : t("reset.cta")}
          </button>
          <p className={styles.formError} role="alert">
            {serverError ? tApi(apiErrorKey(serverError), { minutes: retryMinutes(serverError) }) : null}
          </p>
        </form>
      ) : null}
      <p className={styles.switch}>
        <Link href="/login" className={styles.switchLink}>
          {t("backToLogin")}
        </Link>
      </p>
    </section>
  );
}
