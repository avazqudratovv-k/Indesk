"use client";

import { useId } from "react";
import { useTranslations } from "next-intl";
import styles from "./ConsentBox.module.css";

// Consent checkbox from DECISIONS #16. The state lives only in the page; nothing is sent or stored.
export default function ConsentBox({ checked, onChange }: { checked: boolean; onChange: (checked: boolean) => void }) {
  const t = useTranslations("workspace");
  const id = useId();
  return (
    <label htmlFor={id} className={styles.consent}>
      <input id={id} type="checkbox" className={styles.box} checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{t("consent")}</span>
    </label>
  );
}
