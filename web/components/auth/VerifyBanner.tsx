"use client";

import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/use-session";
import { showVerifyBanner } from "@/lib/auth/verification";
import ResendLink from "./ResendLink";
import styles from "./VerifyBanner.module.css";

// A slim banner on the workspace and My page for a signed-in user whose email is not confirmed. It leaves as soon as
// the session user is verified (the verify page refreshes the session).
export default function VerifyBanner() {
  const t = useTranslations("verify.banner");
  const session = useSession();
  if (!showVerifyBanner(session)) return null;
  return (
    <div className={styles.banner} data-print="hide">
      <p className={styles.text}>{t("text")}</p>
      <ResendLink />
    </div>
  );
}
