// Supported UI languages. Add "ja", "ru", "uz" here (and a messages file) when they are ready.
export const locales = ["en", "ko"] as const;
export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "en";
export const localeCookieName = "NEXT_LOCALE";

// Names are always shown in their own language, as on the design board.
export const localeLabels: Record<Locale, string> = {
  en: "EN",
  ko: "한국어",
};

// Full names for the mobile language menu, also in their own language.
export const localeNames: Record<Locale, string> = {
  en: "English",
  ko: "한국어",
};

export function isLocale(value: string | undefined): value is Locale {
  return locales.some((locale) => locale === value);
}
