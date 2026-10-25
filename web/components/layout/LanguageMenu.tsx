"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { useTranslations } from "next-intl";
import { localeLabels, localeNames, locales, type Locale } from "@/i18n/config";
import { useSetLocale } from "@/i18n/use-set-locale";
import styles from "./LanguageMenu.module.css";

// Mobile language control: a button that opens a listbox BELOW it (replaces the native <select>, whose popup is
// drawn by the browser, small and overlapping the control). Pattern: button with aria-haspopup="listbox";
// focus moves to the listbox, arrows change the active option, Enter or Space picks, Esc or Tab closes.
export default function LanguageMenu() {
  const t = useTranslations("language");
  const { locale, setLocale } = useSetLocale();
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const id = useId();
  const optionId = (index: number) => `${id}-option-${index}`;

  function show() {
    setActive(Math.max(0, locales.indexOf(locale)));
    setOpen(true);
  }

  function close(returnFocus: boolean) {
    setOpen(false);
    if (returnFocus) trigger.current?.focus();
  }

  function pick(code: Locale) {
    setLocale(code);
    close(true);
  }

  // Focus the listbox when it opens, and keep it inside the screen (the trigger sits near the left edge, Korean is wider).
  useLayoutEffect(() => {
    const node = list.current;
    if (!open || !node) return;
    node.focus();
    node.style.transform = "";
    const rect = node.getBoundingClientRect();
    const margin = 8;
    const overflowRight = rect.right - (window.innerWidth - margin);
    if (overflowRight > 0) node.style.transform = `translateX(${-overflowRight}px)`;
    else if (rect.left < margin) node.style.transform = `translateX(${margin - rect.left}px)`;
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (root.current && event.target instanceof Node && !root.current.contains(event.target)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  function onTriggerKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      show();
    }
  }

  function onListKeyDown(event: KeyboardEvent<HTMLUListElement>) {
    switch (event.key) {
      case "ArrowDown":
        event.preventDefault();
        setActive((value) => (value + 1) % locales.length);
        break;
      case "ArrowUp":
        event.preventDefault();
        setActive((value) => (value - 1 + locales.length) % locales.length);
        break;
      case "Home":
        event.preventDefault();
        setActive(0);
        break;
      case "End":
        event.preventDefault();
        setActive(locales.length - 1);
        break;
      case "Enter":
      case " ":
        event.preventDefault();
        pick(locales[active]);
        break;
      case "Escape":
        event.preventDefault();
        close(true);
        break;
      case "Tab":
        // Let focus move on naturally; just close.
        setOpen(false);
        break;
    }
  }

  return (
    <div ref={root} className={styles.root}>
      <button
        ref={trigger}
        type="button"
        className={styles.trigger}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `${id}-list` : undefined}
        aria-label={`${t("label")}: ${localeNames[locale]}`}
        onClick={() => (open ? close(false) : show())}
        onKeyDown={onTriggerKeyDown}
      >
        {localeLabels[locale]}
        <svg className={styles.chevron} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open ? (
        <ul
          ref={list}
          id={`${id}-list`}
          className={styles.list}
          role="listbox"
          tabIndex={-1}
          aria-label={t("label")}
          aria-activedescendant={optionId(active)}
          onKeyDown={onListKeyDown}
        >
          {locales.map((code, index) => (
            <li
              key={code}
              id={optionId(index)}
              role="option"
              aria-selected={code === locale}
              className={`${styles.option} ${index === active ? styles.active : ""}`}
              onPointerEnter={() => setActive(index)}
              onClick={() => pick(code)}
            >
              <span>{localeNames[code]}</span>
              {code === locale ? (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
                  <path d="M5 12.5l4.5 4.5L19 7.5" />
                </svg>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
