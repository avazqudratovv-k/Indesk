"use client";

import { useTranslations } from "next-intl";
import { isLocale, localeLabels, locales } from "@/i18n/config";
import { useSetLocale } from "@/i18n/use-set-locale";
import styles from "./LanguageSwitch.module.css";

// Buttons on desktop, dropdown on mobile (DESIGN.md section 4). CSS shows one of them.
export default function LanguageSwitch() {
  const t = useTranslations("language");
  const { locale, setLocale } = useSetLocale();
  return (
    <>
      <div className={styles.buttons} role="group" aria-label={t("label")}>
        {locales.map((code) => (
          <button key={code} type="button" className={styles.lg} aria-pressed={code === locale} onClick={() => setLocale(code)}>
            {localeLabels[code]}
          </button>
        ))}
      </div>
      <select
        className={styles.select}
        aria-label={t("label")}
        value={locale}
        onChange={(event) => {
          const value = event.target.value;
          if (isLocale(value)) setLocale(value);
        }}
      >
        {locales.map((code) => (
          <option key={code} value={code}>
            {localeLabels[code]}
          </option>
        ))}
      </select>
    </>
  );
}
