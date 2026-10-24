"use client";

import { useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { localeCookieName, type Locale } from "./config";

const ONE_YEAR = 60 * 60 * 24 * 365;

// Language switch helper: stores the choice in a cookie, then refreshes so server components re-render.
export function useSetLocale() {
  const router = useRouter();
  const locale = useLocale();

  function setLocale(next: Locale) {
    if (next === locale) return;
    document.cookie = `${localeCookieName}=${next}; path=/; max-age=${ONE_YEAR}; samesite=lax`;
    router.refresh();
  }

  return { locale, setLocale };
}
