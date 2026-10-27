"use client";

import { useId, useRef } from "react";
import { useTranslations } from "next-intl";
import { MAX_QUESTION_CHARS, MAX_QUESTION_INPUT_CHARS, QUESTION_COUNTER_FROM, questionLength } from "@/lib/workspace/validate";
import styles from "./QuestionBox.module.css";

type Chip = { text: string; full: string };

type Props = {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  chips?: boolean;
  // Keeps the chips' space but shows nothing (the page does not yet know whether to offer them).
  chipsHidden?: boolean;
};

// Question textarea with the board's example chips. The text is trimmed and limited to 1,000 characters when a run starts.
export default function QuestionBox({ value, onChange, placeholder, chips, chipsHidden }: Props) {
  const t = useTranslations("workspace");
  const ids = useId();
  const area = useRef<HTMLTextAreaElement>(null);
  const length = questionLength(value);
  const over = length - MAX_QUESTION_CHARS;
  const tooLong = over > 0;
  const showCounter = length >= QUESTION_COUNTER_FROM;
  const examples = chips ? (t.raw("question.chips") as Chip[]) : [];

  return (
    <div className={styles.box}>
      <label htmlFor={`${ids}-q`} className={styles.srOnly}>
        {t("question.label")}
      </label>
      <textarea
        ref={area}
        id={`${ids}-q`}
        className={styles.area}
        rows={4}
        value={value}
        maxLength={MAX_QUESTION_INPUT_CHARS}
        placeholder={placeholder}
        aria-invalid={tooLong || undefined}
        aria-describedby={tooLong ? `${ids}-err` : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
      <div className={styles.under}>
        <div id={`${ids}-err`} className={styles.error} aria-live="polite">
          {tooLong ? t("question.tooLong", { over, max: MAX_QUESTION_CHARS }) : null}
        </div>
        {showCounter ? (
          <span className={styles.counter} data-over={tooLong || undefined}>
            {t("question.counter", { count: length, max: MAX_QUESTION_CHARS })}
          </span>
        ) : null}
      </div>
      {examples.length > 0 ? (
        <div className={styles.chips} role="group" aria-label={t("question.chipsLabel")} style={chipsHidden ? { visibility: "hidden" } : undefined} aria-hidden={chipsHidden || undefined} inert={chipsHidden || undefined}>
          {examples.map((chip) => (
            <button
              key={chip.text}
              type="button"
              className={styles.chip}
              onClick={() => {
                onChange(chip.full);
                area.current?.focus();
              }}
            >
              {chip.text}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
