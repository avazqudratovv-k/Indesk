"use client";

import { useLayoutEffect, useRef } from "react";
import styles from "./Checkout.module.css";

type CardFieldProps = {
  id: string;
  label: string;
  value: string;
  placeholder: string;
  error?: string;
  locked: boolean;
  // Turns what the user typed or pasted into the allowed, formatted text. `deleting` is true when the text got shorter.
  format: (raw: string, deleting: boolean) => string;
  onValue: (next: string) => void;
};

const countDigits = (text: string) => text.replace(/\D/g, "").length;

// Where the caret belongs in `text` after `digits` digits.
function caretAfter(text: string, digits: number): number {
  if (digits === 0) return 0;
  let seen = 0;
  for (let index = 0; index < text.length; index += 1) {
    if (/\d/.test(text[index])) seen += 1;
    if (seen === digits) return index + 1;
  }
  return text.length;
}

// One numeric card field. The formatted text is the only copy of the value, and it lives in the parent's state.
export default function CardField({ id, label, value, placeholder, error, locked, format, onValue }: CardFieldProps) {
  const input = useRef<HTMLInputElement>(null);
  const caret = useRef<number | null>(null);
  const errorId = `${id}-error`;

  // Formatting rewrites the text, which would throw the caret to the end when editing in the middle.
  useLayoutEffect(() => {
    const element = input.current;
    if (element && caret.current !== null && document.activeElement === element) element.setSelectionRange(caret.current, caret.current);
    caret.current = null;
  }, [value]);

  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <input
        ref={input}
        id={id}
        className={`${styles.input} ${error ? styles.inputBad : ""}`}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        autoCorrect="off"
        spellCheck={false}
        placeholder={placeholder}
        value={value}
        readOnly={locked}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        onChange={(event) => {
          const raw = event.target.value;
          const position = event.target.selectionStart ?? raw.length;
          const next = format(raw, raw.length < value.length);
          caret.current = position >= raw.length ? next.length : caretAfter(next, countDigits(raw.slice(0, position)));
          onValue(next);
        }}
      />
      {error ? (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
