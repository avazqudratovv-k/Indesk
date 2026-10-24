"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/use-session";
import { HomeIcon, MyIcon, PlansIcon, WorkspaceIcon } from "./icons";
import { isActive } from "./nav-items";
import styles from "./TabBar.module.css";

type Tab = { key: "home" | "workspace" | "my" | "plans"; href: string; signedInOnly: boolean; icon: React.ReactNode };

const tabs: Tab[] = [
  { key: "home", href: "/", signedInOnly: false, icon: <HomeIcon /> },
  { key: "workspace", href: "/workspace", signedInOnly: false, icon: <WorkspaceIcon /> },
  { key: "my", href: "/my", signedInOnly: true, icon: <MyIcon /> },
  { key: "plans", href: "/plans", signedInOnly: false, icon: <PlansIcon /> },
];

// Signed in: Home, Workspace, My, Plans. Signed out: Home, Workspace, Plans (DECISIONS #62).
export default function TabBar() {
  const t = useTranslations("tabBar");
  const pathname = usePathname();
  const session = useSession();

  return (
    <nav className={styles.tabbar} aria-label={t("label")}>
      {tabs
        .filter((tab) => session.signedIn || !tab.signedInOnly)
        .map((tab) => {
          const active = isActive(pathname, tab.href);
          return (
            <Link key={tab.key} href={tab.href} className={`${styles.tab} ${active ? styles.on : ""}`} aria-current={active ? "page" : undefined}>
              {tab.icon}
              <span className={styles.label}>{t(tab.key)}</span>
            </Link>
          );
        })}
    </nav>
  );
}
