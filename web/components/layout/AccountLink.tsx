"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import styles from "./Navbar.module.css";

// The signed-in display name in the desktop navbar, as a link to My page. The accessible name says where it goes.
// Only /my itself is "current" (the nav's My reports link also covers report pages; this link names the page, not the area).
export default function AccountLink({ name }: { name: string }) {
  const t = useTranslations("nav");
  const current = usePathname() === "/my";
  return (
    <Link
      href="/my"
      className={`${styles.link} ${styles.who} ${styles.whoLink} ${current ? styles.on : ""}`}
      aria-current={current ? "page" : undefined}
      aria-label={t("accountLink", { name })}
    >
      {name}
    </Link>
  );
}
