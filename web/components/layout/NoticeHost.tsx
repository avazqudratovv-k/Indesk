"use client";

import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { consumeNotice, noticeMessage, NOTICE_EVENT, type Notice } from "@/lib/auth/notice";
import styles from "./NoticeHost.module.css";

const dismissAfterMs = 6000;

function pending(): Notice | null {
  try {
    return consumeNotice(window.sessionStorage);
  } catch {
    return null;
  }
}

// The region is always in the page and empty, so a screen reader announces text that is inserted later. A notice is
// read once from sessionStorage (on mount, and when one is posted while the page stays open), then dismissed by the
// close button or after about 6 s; the timer waits while focus is inside.
export default function NoticeHost() {
  const t = useTranslations("notice");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [focused, setFocused] = useState(false);

  const take = useCallback(() => {
    const next = pending();
    if (next) setNotice(next);
  }, []);

  useEffect(() => {
    // Read after mount, not inside the effect body (the notice is browser-only, so the server render is always empty).
    const first = window.setTimeout(take, 0);
    window.addEventListener(NOTICE_EVENT, take);
    return () => {
      window.clearTimeout(first);
      window.removeEventListener(NOTICE_EVENT, take);
    };
  }, [take]);

  useEffect(() => {
    if (!notice || focused) return;
    const timer = window.setTimeout(() => setNotice(null), dismissAfterMs);
    return () => window.clearTimeout(timer);
  }, [notice, focused]);

  const message = notice ? noticeMessage(notice) : null;
  return (
    <div className={styles.region} role="status" aria-live="polite">
      {message ? (
        <div className={styles.notice} onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}>
          <p className={styles.text}>{t(message.key, message.values)}</p>
          <button
            type="button"
            className={styles.close}
            aria-label={t("close")}
            onClick={() => {
              setFocused(false);
              setNotice(null);
            }}
          >
            <span aria-hidden="true">×</span>
          </button>
        </div>
      ) : null}
    </div>
  );
}
