import { useTranslations } from "next-intl";
import styles from "./ViewToggle.module.css";

export type ReportViewMode = "simple" | "detailed";

// Simple / Detailed switch (board: a group of two `aria-pressed` buttons).
export default function ViewToggle({ value, onChange }: { value: ReportViewMode; onChange: (next: ReportViewMode) => void }) {
  const t = useTranslations("report.view");
  return (
    <div className={styles.group} role="group" aria-label={t("label")}>
      {(["simple", "detailed"] as const).map((view) => (
        <button key={view} type="button" className={styles.button} aria-pressed={value === view} onClick={() => onChange(view)}>
          {t(view)}
        </button>
      ))}
    </div>
  );
}
