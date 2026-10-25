"use client";

import { useRef, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import type { WorkspaceMode } from "@/lib/workspace/validate";
import styles from "./ModeSwitch.module.css";

const modes: WorkspaceMode[] = ["ask", "check", "compare"];

// Board mode switch: a radio group (Ask / Check a document / Compare) with a one-line hint under it.
export default function ModeSwitch({ mode, onChange }: { mode: WorkspaceMode; onChange: (mode: WorkspaceMode) => void }) {
  const t = useTranslations("workspace");
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);

  function onKeyDown(event: KeyboardEvent, index: number) {
    const last = modes.length - 1;
    const next =
      event.key === "ArrowRight" || event.key === "ArrowDown"
        ? (index + 1) % modes.length
        : event.key === "ArrowLeft" || event.key === "ArrowUp"
          ? (index + last) % modes.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? last
              : -1;
    if (next < 0) return;
    event.preventDefault();
    onChange(modes[next]);
    buttons.current[next]?.focus();
  }

  return (
    <div>
      <div className={styles.modes} role="radiogroup" aria-label={t("modes.label")}>
        {modes.map((value, index) => (
          <button
            key={value}
            ref={(node) => {
              buttons.current[index] = node;
            }}
            type="button"
            role="radio"
            className={styles.mode}
            aria-checked={mode === value}
            tabIndex={mode === value ? 0 : -1}
            onClick={() => onChange(value)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {t(`modes.${value}`)}
          </button>
        ))}
      </div>
      <p className={styles.hint}>{t(`modes.intro.${mode}`)}</p>
    </div>
  );
}
