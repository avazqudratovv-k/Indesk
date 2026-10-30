"use client";

import { useTranslations } from "next-intl";
import { useSession } from "@/hooks/use-session";
import { displayInitial, planKey } from "@/lib/my/display";
import styles from "./my.module.css";

// Avatar, title and "{email} · {plan}", all from the session. No Pro toggle (the board's demo switch is not built).
export default function MyHeader() {
  const t = useTranslations("my");
  const { user } = useSession();
  return (
    <div className={styles.header}>
      <span className={styles.avatar} aria-hidden="true">
        {user ? displayInitial(user.display_name) : ""}
      </span>
      <div className={styles.headerText}>
        <h1 className={styles.title}>{t("title")}</h1>
        {user ? <p className={styles.headerLine}>{t("header.line", { address: user.email, plan: t(`plan.${planKey(user.plan)}`) })}</p> : null}
      </div>
    </div>
  );
}
