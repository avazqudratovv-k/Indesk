import { cookies } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import { defaultLocale, isLocale, localeCookieName } from "./config";

// No locale prefix in the URL: the locale comes from a cookie (ROADMAP 1.6).
export default getRequestConfig(async () => {
  const cookieValue = (await cookies()).get(localeCookieName)?.value;
  const locale = isLocale(cookieValue) ? cookieValue : defaultLocale;
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  };
});
