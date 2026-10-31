"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/use-session";
import { HomeIcon, MyIcon, PlansIcon, WorkspaceIcon } from "./icons";
import { isActive, visibleNavItems } from "./nav-items";
import styles from "./TabBar.module.css";

type Tab = { key: "home" | "workspace" | "my" | "plans"; href: string; icon: React.ReactNode };

const tabs: Tab[] = [
  { key: "home", href: "/", icon: <HomeIcon /> },
  { key: "workspace", href: "/workspace", icon: <WorkspaceIcon /> },
  { key: "my", href: "/my", icon: <MyIcon /> },
  { key: "plans", href: "/plans", icon: <PlansIcon /> },
];

// Shown or hidden by the same `built` / `signedInOnly` flags as the desktop links (nav-items.ts).
const visibleTabs = (signedIn: boolean) => {
  const shown = new Set(visibleNavItems(signedIn).map((item) => item.href));
  return tabs.filter((tab) => shown.has(tab.href));
};

// Floating pill: the active tab is a chip with icon and label, the others show the icon only.
// Today: Home, Workspace, Plans. My comes back with `built: true` in nav-items.ts (DECISIONS #62).
export default function TabBar() {
  const t = useTranslations("tabBar");
  const pathname = usePathname();
  const session = useSession();

  return (
    <nav data-print="hide" className={styles.tabbar} aria-label={t("label")}>
      {visibleTabs(session.signedIn)
        .map((tab) => {
          const active = isActive(pathname, tab.href);
          return (
            <Link key={tab.key} href={tab.href} className={`${styles.tab} ${active ? styles.on : ""}`} aria-label={t(tab.key)} aria-current={active ? "page" : undefined}>
              {tab.icon}
              {active ? <span className={styles.label}>{t(tab.key)}</span> : null}
            </Link>
          );
        })}
    </nav>
  );
}
