import type { Locale } from "./i18n/config";
import type en from "./messages/en.json";

// Typed translation keys: a missing or misspelled key fails the typecheck.
declare module "next-intl" {
  interface AppConfig {
    Locale: Locale;
    Messages: typeof en;
  }
}
