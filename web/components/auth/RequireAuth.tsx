"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect } from "react";
import { useSession } from "@/hooks/use-session";
import { loginHref } from "@/lib/auth/safe-next";
import styles from "./RequireAuth.module.css";

// Wraps a signed-in-only page. Unknown shows a neutral placeholder (no Log in prompt for someone who is signed in);
// signed out goes to /login and comes back to this path afterwards.
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const t = useTranslations("common");
  const session = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const signedOut = session.status === "signedOut";

  useEffect(() => {
    if (signedOut) router.replace(loginHref(search ? `${pathname}?${search}` : pathname));
  }, [signedOut, router, pathname, search]);

  if (session.status === "signedIn") return children;
  return (
    <main className={styles.placeholder} aria-busy="true">
      <p className={styles.label} role="status">
        {t("loading")}
      </p>
    </main>
  );
}
