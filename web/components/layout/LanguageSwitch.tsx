"use client";

import { useTranslations } from "next-intl";
import { localeLabels, locales } from "@/i18n/config";
import { useSetLocale } from "@/i18n/use-set-locale";
import LanguageMenu from "./LanguageMenu";
import styles from "./LanguageSwitch.module.css";

// Buttons on desktop, a dropdown menu on phones (DESIGN.md section 4). CSS shows one of them.
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
      <LanguageMenu />
    </>
  );
}
