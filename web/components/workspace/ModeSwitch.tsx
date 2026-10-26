"use client";

import { useRef, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import type { WorkspaceMode } from "@/lib/workspace/validate";
import styles from "./ModeSwitch.module.css";

const modes: WorkspaceMode[] = ["ask", "check", "compare"];
// Only Ask works for now (the API refuses the others). The rest are shown but cannot be chosen.
const available = new Set<WorkspaceMode>(["ask"]);

// Board mode switch: a radio group (Ask / Check a document / Compare) with a one-line hint under it.
// Unavailable modes use aria-disabled, are skipped by the arrow keys and the Tab order (like disabled radios),
// and say "Coming soon" in text.
export default function ModeSwitch({ mode, onChange }: { mode: WorkspaceMode; onChange: (mode: WorkspaceMode) => void }) {
  const t = useTranslations("workspace");
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent, index: number) {
    const usable = modes.map((value, position) => (available.has(value) ? position : -1)).filter((position) => position >= 0);
    const at = usable.indexOf(index);
    const next =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? usable[(at + 1) % usable.length]
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? usable[(at + usable.length - 1) % usable.length]
          : event.key === "Home"
            ? usable[0]
            : event.key === "End"
              ? usable[usable.length - 1]
              : undefined;
    if (next === undefined) return;
    event.preventDefault();
    onChange(modes[next]);
    buttons.current[next]?.focus();
  }

  return (
    <div>
      <div className={styles.modes} role="radiogroup" aria-label={t("modes.label")}>
        {modes.map((value, index) => {
          const usable = available.has(value);
          return (
            <button
              key={value}
              ref={(node) => {
                buttons.current[index] = node;
              }}
              type="button"
              role="radio"
              className={styles.mode}
              aria-checked={mode === value}
              aria-disabled={usable ? undefined : true}
              tabIndex={usable && mode === value ? 0 : -1}
              onClick={usable ? () => onChange(value) : undefined}
              onKeyDown={usable ? (event) => onKeyDown(event, index) : undefined}
            >
              {usable ? t(`modes.${value}`) : <span className={styles.name}>{t(`modes.${value}`)}</span>}
              {usable ? null : <span className={styles.soon}>{t("modes.soon")}</span>}
            </button>
          );
        })}
      </div>
      <p className={styles.hint}>{t(`modes.intro.${mode}`)}</p>
    </div>
  );
}
