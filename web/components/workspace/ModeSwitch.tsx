"use client";

import { useTranslations } from "next-intl";
import type { WorkspaceMode } from "@/lib/workspace/validate";
import styles from "./ModeSwitch.module.css";

const modes: WorkspaceMode[] = ["ask", "check", "compare"];
// Only Ask works for now (the API refuses the others). The rest are shown but cannot be chosen.
const available = new Set<WorkspaceMode>(["ask"]);

// Board mode switch: a radio group (Ask / Check a document / Compare) with a one-line hint under it.
// Only Ask can be chosen, and it already is, so nothing here changes the mode. The other two use aria-disabled, are
// left out of the Tab order (like disabled radios) and say "Not available yet" in text.
export default function ModeSwitch({ mode }: { mode: WorkspaceMode }) {
  const t = useTranslations("workspace");
  return (
    <div>
      <div className={styles.modes} role="radiogroup" aria-label={t("modes.label")}>
        {modes.map((value) => {
          const usable = available.has(value);
          return (
            <button
              key={value}
              type="button"
              role="radio"
              className={styles.mode}
              aria-checked={mode === value}
              aria-disabled={usable ? undefined : true}
              tabIndex={usable && mode === value ? 0 : -1}
            >
              {usable ? t(`modes.${value}`) : <span className={styles.name}>{t(`modes.${value}`)}</span>}
              {usable ? null : <span className={styles.soon}>{t("modes.soon")}</span>}
            </button>
          );
        })}
      </div>
      <p className={styles.hint}>{t("modes.intro.ask")}</p>
    </div>
  );
}
