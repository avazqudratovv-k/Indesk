"use client";

import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import RealRunView from "./run/RealRunView";
import type { LiveRunApi } from "./run/use-live-run";
import styles from "./RunTab.module.css";

// The run tab for real runs (ROADMAP 4.3): the live view of the person's latest run, or the "nothing yet" card.
export default function RealRunTab({ live, onBack }: { live: LiveRunApi; onBack: () => void }) {
  const t = useTranslations("workspace");
  if (!live.run) {
    return (
      <section className={styles.peek}>
        <div>
          <b className={styles.peekTitle}>{t("runTab.peekTitle")}</b>
          <p className={styles.peekSub}>{t("runTab.peekSub")}</p>
        </div>
        <Button onClick={onBack}>{t("runTab.goAsk")}</Button>
      </section>
    );
  }
  return <RealRunView key={live.run.id} run={live.run} connection={live.connection} onReconnect={live.reconnect} onBack={onBack} />;
}
