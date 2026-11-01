"use client";

import VerifyBanner from "@/components/auth/VerifyBanner";
import DemoNotice from "@/components/ui/DemoNotice";
import AccountCard from "./AccountCard";
import FilesSection from "./FilesSection";
import MyHeader from "./MyHeader";
import ReportsSection from "./ReportsSection";
import UsageCard from "./UsageCard";
import styles from "./my.module.css";

// My page: header, then the lists on the left and usage plus account on the right (board). On phones the right column
// comes first: usage, account, reports, files.
export default function MyView() {
  return (
    <main className={styles.main}>
      <VerifyBanner />
      <MyHeader />
      <div className={styles.columns}>
        <div className={styles.primary}>
          <ReportsSection />
          <FilesSection />
        </div>
        <div className={styles.aside}>
          <UsageCard />
          <AccountCard />
        </div>
      </div>
      <DemoNotice />
    </main>
  );
}
