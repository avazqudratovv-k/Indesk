"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useId, useRef, useState, type FormEvent } from "react";
import { devSessionCookie, devSwitchEnabled } from "@/lib/session";
import { validateAuth, type AuthErrors, type AuthField, type AuthMode, type AuthValues } from "./validate";
import styles from "./AuthForm.module.css";

type Status = "idle" | "submitting" | "signedIn" | "demo";

const emptyValues: AuthValues = { name: "", email: "", password: "" };
const fakeDelayMs = 900;

// Fake submit only (ROADMAP 2.2 and 2.3): validates on the client, shows loading and a result, and stops.
// Nothing is sent, stored, logged or echoed. Real auth arrives at ROADMAP 4.1.
export default function AuthForm({ mode }: { mode: AuthMode }) {
  const t = useTranslations("auth");
  const router = useRouter();
  const ids = useId();
  const nameRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [values, setValues] = useState<AuthValues>(emptyValues);
  const [errors, setErrors] = useState<AuthErrors>({});
  const [showPassword, setShowPassword] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const signup = mode === "signup";
  const otherHref = signup ? "/login" : "/signup";

  function update(field: AuthField, value: string) {
    setValues((current) => ({ ...current, [field]: value }));
    if (errors[field]) setErrors((current) => ({ ...current, [field]: undefined }));
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
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
    setStatus("submitting");
    window.setTimeout(() => {
      // Development builds only: the same mock session cookie the dev switch uses. Production signs no one in.
      if (devSwitchEnabled) {
        document.cookie = `${devSessionCookie}=in; path=/; max-age=${60 * 60 * 24 * 30}; samesite=lax`;
        setStatus("signedIn");
        router.push("/workspace");
        router.refresh();
      } else {
        setStatus("demo");
      }
    }, fakeDelayMs);
  }

  const busy = status === "submitting";
  const fieldId = (field: AuthField) => `${ids}-${field}`;
  const errorId = (field: AuthField) => `${ids}-${field}-error`;

  function describedBy(field: AuthField, hint = false) {
    return [errors[field] ? errorId(field) : "", hint ? `${ids}-hint` : ""].filter(Boolean).join(" ") || undefined;
  }

  function error(field: AuthField) {
    const key = errors[field];
    return (
      <p id={errorId(field)} className={styles.error} aria-live="polite">
        {key ? t(`errors.${key}`) : null}
      </p>
    );
  }

  return (
    <section className={styles.card} aria-labelledby={`${ids}-title`}>
      <nav className={styles.tabs} aria-label={t("tabsLabel")}>
        <Link href="/signup" className={`${styles.tab} ${signup ? styles.tabOn : ""}`} aria-current={signup ? "page" : undefined}>
          {t("tabSignup")}
        </Link>
        <Link href="/login" className={`${styles.tab} ${signup ? "" : styles.tabOn}`} aria-current={signup ? undefined : "page"}>
          {t("tabLogin")}
        </Link>
      </nav>
      <div>
        <h1 id={`${ids}-title`} className={styles.title}>
          {t(`${mode}.title`)}
        </h1>
        <p className={styles.sub}>{t(`${mode}.sub`)}</p>
      </div>
      <form className={styles.form} onSubmit={onSubmit} noValidate aria-busy={busy}>
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
            aria-invalid={errors.email ? true : undefined}
            aria-describedby={describedBy("email")}
          />
          {error("email")}
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
        </div>
        <button type="submit" className={styles.cta} disabled={busy || status === "signedIn"}>
          {busy ? t(`${mode}.submitting`) : t(`${mode}.cta`)}
        </button>
        <p className={styles.result} role="status">
          {status === "signedIn" ? t("success.dev") : status === "demo" ? t("success.demo") : null}
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
