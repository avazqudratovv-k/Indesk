import { useTranslations } from "next-intl";
import { TOOL_CALL_LIMIT } from "@/lib/run/mock-run";
import styles from "./GuardrailsPanel.module.css";

// Board "Guardrails in this run". Limits come from AGENTS.md: step cap 12, a spending cap per run, sandbox without
// network, originals deleted after 24 h. The amounts are internal and not shown (DECISIONS #74).
export default function GuardrailsPanel() {
  const t = useTranslations("workspace");
  const rows = [
    { label: t("live.guard.tools"), value: String(TOOL_CALL_LIMIT) },
    { label: t("live.guard.budget"), value: t("live.guard.budgetValue") },
    { label: t("live.guard.network"), value: t("live.guard.networkValue") },
    { label: t("live.guard.files"), value: t("live.guard.filesValue") },
  ];
  return (
    <section className={styles.panel} aria-labelledby="ws-guard-title">
      <h2 id="ws-guard-title" className={styles.title}>
        {t("live.guard.title")}
      </h2>
      <dl className={styles.rows}>
        {rows.map((row) => (
          <div key={row.label} className={styles.row}>
            <dt>{row.label}</dt>
            <dd>{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
