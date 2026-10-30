"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { useSession, useSessionActions } from "@/hooks/use-session";
import BrandMark from "./BrandMark";
import LanguageSwitch from "./LanguageSwitch";
import ThemeToggle from "./ThemeToggle";
import { isActive, visibleNavItems } from "./nav-items";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const session = useSession();
  const { endSession } = useSessionActions();
  const router = useRouter();
  const onAuthPage = pathname === "/login" || pathname === "/signup";
  const authHidden = onAuthPage ? styles.authPageHidden : "";
  const [tapped, setTapped] = useState(false);
  const tapTimer = useRef<number | undefined>(undefined);
  const [logout, setLogout] = useState<"idle" | "busy" | "failed">("idle");
  const failTimer = useRef<number | undefined>(undefined);

  useEffect(
    () => () => {
      window.clearTimeout(tapTimer.current);
      window.clearTimeout(failTimer.current);
    },
    [],
  );

  // Logs out on the server first. If the server cannot be reached the session is still active, so say that.
  async function onLogout() {
    if (logout === "busy") return;
    setLogout("busy");
    try {
      await endSession();
      setLogout("idle");
      router.push("/");
    } catch {
      setLogout("failed");
      window.clearTimeout(failTimer.current);
      failTimer.current = window.setTimeout(() => setLogout("idle"), 4000);
    }
  }

  // Tilts the mark for 600 ms on click or tap. The link still navigates; nothing is prevented.
  function tapBrand() {
    window.clearTimeout(tapTimer.current);
    setTapped(true);
    tapTimer.current = window.setTimeout(() => setTapped(false), 600);
  }

  return (
    <header className={`${styles.mast} ${session.signedIn ? styles.compact : ""}`}>
      <div className={styles.inner}>
        <Link href="/" className={`${styles.brand} ${tapped ? styles.tap : ""}`} aria-label={t("brand")} onClick={tapBrand}>
          <BrandMark />
          <span className={styles.brandName}>indesk</span>
        </Link>

        <nav className={styles.nav} aria-label={t("main")}>
          {visibleNavItems(session.signedIn)
            .map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link key={item.key} href={item.href} className={`${styles.link} ${active ? styles.on : ""}`} aria-current={active ? "page" : undefined}>
                  {t(item.key)}
                </Link>
              );
            })}
        </nav>

        <div className={styles.right}>
          <LanguageSwitch />
          <ThemeToggle />
          {/* The slot is as wide as the wider answer (Log in + Sign up, or name + Log out) in every state, so the bar
              does not move when the session becomes known. The two invisible layers only hold the room; they are hidden
              from everyone and cannot be focused. */}
          <span className={styles.slot}>
            <span className={styles.ghost} aria-hidden="true" inert>
              <span className={`${styles.link} ${styles.login}`}>{t("login")}</span>
              <Button variant="primary" size="sm" tabIndex={-1}>
                {t("signup")}
              </Button>
            </span>
            <span className={styles.ghost} aria-hidden="true" inert>
              <span className={`${styles.link} ${styles.who}`}>WWWWWWWW</span>
              <span className={`${styles.link} ${styles.plainButton}`}>{t("logout")}</span>
            </span>
            <span className={styles.live}>
              {session.status === "unknown" ? null : session.user ? (
                <>
                  <span className={`${styles.link} ${styles.who}`}>{session.user.display_name}</span>
                  <button type="button" className={`${styles.link} ${styles.plainButton}`} onClick={onLogout} disabled={logout === "busy"} aria-live="polite">
                    {logout === "busy" ? t("logoutBusy") : logout === "failed" ? t("logoutFailed") : t("logout")}
                  </button>
                </>
              ) : (
                <>
                  <Link href="/login" className={`${styles.link} ${styles.login} ${authHidden}`}>
                    {t("login")}
                  </Link>
                  <Button href="/signup" variant="primary" size="sm" className={authHidden}>
                    {t("signup")}
                  </Button>
                </>
              )}
            </span>
          </span>
        </div>
      </div>
    </header>
  );
}
