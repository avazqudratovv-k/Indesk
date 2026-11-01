"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useSession, useSessionActions } from "@/hooks/use-session";
import { ApiError, apiErrorKey, retryMinutes } from "@/lib/api/errors";
import { login, signup as signupRequest } from "@/lib/auth/api";
import { dropPendingSessionEnded, postNotice } from "@/lib/auth/notice";
import { mailLang } from "@/lib/auth/recovery";
import { safeNext } from "@/lib/auth/safe-next";
import { validateAuth, type AuthErrors, type AuthField, type AuthMode, type AuthValues } from "./validate";
import styles from "./AuthForm.module.css";

type Status = "idle" | "submitting" | "done";

const emptyValues: AuthValues = { name: "", email: "", password: "" };
const afterAuthDefault = "/workspace";

// Validates on the client, then calls the real API. Only an error code is ever shown, never server text.
// Credentials are never stored or logged. `next` is where to go afterwards (a safe same-origin path or nothing).
export default function AuthForm({ mode, next }: { mode: AuthMode; next?: string }) {
  const t = useTranslations("auth");
  const tApi = useTranslations("apiErrors");
  const locale = useLocale();
  const session = useSession();
  const { startSession } = useSessionActions();
  const router = useRouter();
  const ids = useId();
  const nameRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [values, setValues] = useState<AuthValues>(emptyValues);
  const [errors, setErrors] = useState<AuthErrors>({});
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [serverError, setServerError] = useState<ApiError | null>(null);
  const signup = mode === "signup";
  const destination = safeNext(next) ?? afterAuthDefault;
  const otherPath = signup ? "/login" : "/signup";
  const otherHref = next && safeNext(next) ? `${otherPath}?next=${encodeURIComponent(safeNext(next)!)}` : otherPath;
  const emailTaken = serverError?.code === "EMAIL_TAKEN";

  // Someone already signed in has no use for these pages.
  useEffect(() => {
    if (session.signedIn) router.replace(destination);
  }, [session.signedIn, router, destination]);

  function message(error: ApiError): string {
    return tApi(apiErrorKey(error), { minutes: retryMinutes(error) });
  }

  function update(field: AuthField, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    if (serverError) setServerError(null);
    if (errors[field]) setErrors((current) => ({ ...current, [field]: undefined }));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (status === "submitting") return;
    const found = validateAuth(mode, values);
    setErrors(found);
    const order: AuthField[] = signup ? ["name", "email", "password"] : ["email", "password"];
    const firstBad = order.find((field) => found[field]);
    if (firstBad) {
      const target = { name: nameRef, email: emailRef, password: passwordRef }[firstBad];
      target.current?.focus();
      return;
    }
    setServerError(null);
    setStatus("submitting");
    try {
      const email = values.email.trim();
      const user = signup
        ? await signupRequest({ email, password: values.password, displayName: values.name.trim(), lang: mailLang(locale) })
        : await login({ email, password: values.password });
      setValues((current) => ({ ...current, password: "" }));
      setStatus("done");
      // A login says welcome (this also replaces any pending "session ended"); a signup only drops that old notice.
      if (signup) dropPendingSessionEnded();
      else postNotice({ kind: "welcome", name: user.display_name });
      startSession(user);
      router.replace(destination);
    } catch (caught) {
      const error = caught instanceof ApiError ? caught : new ApiError(0, "UNKNOWN");
      setStatus("idle");
      setServerError(error);
      if (error.code === "EMAIL_TAKEN") emailRef.current?.focus();
    }
  }

  const busy = status === "submitting";
  const fieldId = (field: AuthField) => `${ids}-${field}`;
  const errorId = (field: AuthField) => `${ids}-${field}-error`;

  function describedBy(field: AuthField, hint = false) {
    const shown = errors[field] || (field === "email" && emailTaken);
    return [shown ? errorId(field) : "", hint ? `${ids}-hint` : ""].filter(Boolean).join(" ") || undefined;
  }

  function error(field: AuthField, serverMessage?: string) {
    const key = errors[field];
    return (
      <p id={errorId(field)} className={styles.error} aria-live="polite">
        {key ? t(`errors.${key}`) : (serverMessage ?? null)}
      </p>
    );
  }

  return (
    <section className={styles.card} aria-labelledby={`${ids}-title`}>
      <nav className={styles.tabs} aria-label={t("tabsLabel")}>
        <Link href={signup ? "/signup" : otherHref} className={`${styles.tab} ${signup ? styles.tabOn : ""}`} aria-current={signup ? "page" : undefined}>
          {t("tabSignup")}
        </Link>
        <Link href={signup ? otherHref : "/login"} className={`${styles.tab} ${signup ? "" : styles.tabOn}`} aria-current={signup ? undefined : "page"}>
          {t("tabLogin")}
        </Link>
      </nav>
      <div>
        <h1 id={`${ids}-title`} className={styles.title}>
          {t(`${mode}.title`)}
        </h1>
        <p className={styles.sub}>{t(`${mode}.sub`)}</p>
      </div>
      {/* method="post": if the form is ever submitted natively (before the page is ready), credentials never go into the URL. */}
      <form className={styles.form} method="post" onSubmit={onSubmit} noValidate aria-busy={busy}>
        {signup ? (
          <div className={styles.field}>
            <label htmlFor={fieldId("name")} className={styles.label}>
              {t("name")}
            </label>
            <input
              ref={nameRef}
              id={fieldId("name")}
              name="name"
              type="text"
              autoComplete="name"
              placeholder={t("namePlaceholder")}
              value={values.name}
              onChange={(event) => update("name", event.target.value)}
              className={styles.input}
              aria-invalid={errors.name ? true : undefined}
              aria-describedby={describedBy("name")}
            />
            {error("name")}
          </div>
        ) : null}
        <div className={styles.field}>
          <label htmlFor={fieldId("email")} className={styles.label}>
            {t("email")}
          </label>
          <input
            ref={emailRef}
            id={fieldId("email")}
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder={t("emailPlaceholder")}
            value={values.email}
            onChange={(event) => update("email", event.target.value)}
            className={styles.input}
            aria-invalid={errors.email || emailTaken ? true : undefined}
            aria-describedby={describedBy("email")}
          />
          {error("email", emailTaken && serverError ? message(serverError) : undefined)}
        </div>
        <div className={styles.field}>
          <div className={styles.labelRow}>
            <label htmlFor={fieldId("password")} className={styles.label}>
              {t("password")}
            </label>
            <button
              type="button"
              className={styles.toggle}
              onClick={() => setShowPassword((current) => !current)}
              aria-pressed={showPassword}
              aria-controls={fieldId("password")}
            >
              {showPassword ? t("hide") : t("show")}
            </button>
          </div>
          <input
            ref={passwordRef}
            id={fieldId("password")}
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete={signup ? "new-password" : "current-password"}
            placeholder={t("passwordPlaceholder")}
            value={values.password}
            onChange={(event) => update("password", event.target.value)}
            className={styles.input}
            aria-invalid={errors.password ? true : undefined}
            aria-describedby={describedBy("password", signup)}
          />
          {signup ? (
            <span id={`${ids}-hint`} className={styles.hint}>
              {t("passwordHint")}
            </span>
          ) : null}
          {error("password")}
          {signup ? null : (
            <Link href="/forgot-password" className={styles.forgot}>
              {t("forgotLink")}
            </Link>
          )}
        </div>
        <button type="submit" className={styles.cta} disabled={busy || status === "done"}>
          {busy ? t(`${mode}.submitting`) : t(`${mode}.cta`)}
        </button>
        <p className={styles.formError} role="alert">
          {serverError && !emailTaken ? message(serverError) : null}
        </p>
      </form>
      <p className={styles.switch}>
        {t(`${mode}.switchText`)}{" "}
        <Link href={otherHref} className={styles.switchLink}>
          {t(`${mode}.switchLink`)}
        </Link>
      </p>
    </section>
  );
}
