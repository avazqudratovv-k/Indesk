"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/use-session";
import { devSessionCookie, devSwitchEnabled } from "@/lib/session";
import styles from "./DevSessionSwitch.module.css";

// Dev-only floating control: flips the dev_session cookie and refreshes. Not rendered in production.
export default function DevSessionSwitch() {
  const t = useTranslations("dev.mock");
  const router = useRouter();
  const session = useSession();

  if (!devSwitchEnabled) return null;

  const next = session.signedIn ? "out" : "in";
  function flip() {
    document.cookie = `${devSessionCookie}=${next}; path=/; max-age=${60 * 60 * 24 * 30}; samesite=lax`;
    router.refresh();
  }

  return (
    <button type="button" className={styles.switch} onClick={flip} aria-pressed={session.signedIn} aria-label={t("switchLabel")}>
      {t("switchLabel")}: {session.signedIn ? t("signedIn") : t("signedOut")}
    </button>
  );
}
