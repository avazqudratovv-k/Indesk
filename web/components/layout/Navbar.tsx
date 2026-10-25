"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { useSession } from "@/hooks/use-session";
import BrandMark from "./BrandMark";
import LanguageSwitch from "./LanguageSwitch";
import ThemeToggle from "./ThemeToggle";
import { isActive, navItems } from "./nav-items";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const session = useSession();
  const onAuthPage = pathname === "/login" || pathname === "/signup";
  const authHidden = onAuthPage ? styles.authPageHidden : "";

  return (
    <header className={styles.mast}>
      <div className={styles.inner}>
        <Link href="/" className={styles.brand} aria-label={t("brand")}>
          <BrandMark />
          <span className={styles.brandName}>indesk</span>
        </Link>

        <nav className={styles.nav} aria-label={t("main")}>
          {navItems
            .filter((item) => session.signedIn || !item.signedInOnly)
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
          {session.user ? (
            <Link href="/my" className={styles.avatar} aria-label={t("account", { name: session.user.display_name })}>
              {session.user.display_name.slice(0, 1).toUpperCase()}
            </Link>
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
        </div>
      </div>
    </header>
  );
}
