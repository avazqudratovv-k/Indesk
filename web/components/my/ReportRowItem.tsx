"use client";

import { useFormatter, useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { deleteReport, type ReportRow } from "@/lib/my/api";
import ConfirmDelete from "./ConfirmDelete";
import styles from "./my.module.css";

export default function ReportRowItem({ row, onDeleted }: { row: ReportRow; onDeleted: (id: string) => void }) {
  const t = useTranslations("my.reports");
  const format = useFormatter();
  const date = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "medium" });
  const perfect = row.verified === row.total;

  return (
    <li className={`${styles.row} ${perfect ? styles.rowOk : styles.rowPartial}`}>
      <div className={styles.rowMain}>
        <h3 className={styles.rowTitle}>{row.title}</h3>
        <p className={styles.rowMeta}>
          {t("created", { date: date(row.createdAt) })}
          {" · "}
          {t("files", { count: row.fileCount })}
        </p>
      </div>
      <div className={styles.rowStatus}>
        <Chip tone={row.outcome === "answered" ? "ok" : "warn"}>{t(`outcome.${row.outcome}`)}</Chip>
        <span className={styles.rowFact}>{t("verified", { verified: row.verified, total: row.total })}</span>
        <span className={styles.rowFact}>{t("until", { date: date(row.expiresAt) })}</span>
      </div>
      <div className={styles.rowActions}>
        <Button size="sm" variant="primary" href={`/reports/${row.id}`}>
          {t("open")}
        </Button>
        <ConfirmDelete
          labels={{ delete: t("delete"), confirm: t("confirm"), cancel: t("cancel"), confirmDelete: t("confirmDelete"), deleting: t("deleting") }}
          run={() => deleteReport(row.id)}
          onDone={() => onDeleted(row.id)}
        />
      </div>
    </li>
  );
}
