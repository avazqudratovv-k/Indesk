"use client";

import { useTranslations } from "next-intl";
import DemoNotice from "@/components/ui/DemoNotice";
import FilesSection from "./FilesSection";
import ReportsSection from "./ReportsSection";
import styles from "./my.module.css";

// My page, part A: the reports and files lists. The usage card and the account settings come in later parts.
export default function MyView() {
  const t = useTranslations("my");
  return (
    <main className={styles.main}>
      <h1 className={styles.title}>{t("title")}</h1>
      <ReportsSection />
      <FilesSection />
      <DemoNotice />
    </main>
  );
}
