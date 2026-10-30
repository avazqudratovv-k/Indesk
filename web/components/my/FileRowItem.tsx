"use client";

import { useFormatter, useTranslations } from "next-intl";
import { deleteFile, hoursLeft, type FileRow } from "@/lib/my/api";
import ConfirmDelete from "./ConfirmDelete";
import styles from "./my.module.css";

const kindColor: Record<FileRow["kind"], string> = {
  csv: styles.kindCsv,
  pdf: styles.kindPdf,
  jpg: styles.kindImage,
  png: styles.kindImage,
  txt: styles.kindText,
};

function sizeLabel(bytes: number, number: (n: number, o: { maximumFractionDigits: number }) => string): string {
  if (bytes >= 1_000_000) return `${number(bytes / 1_000_000, { maximumFractionDigits: 1 })} MB`;
  return `${number(Math.max(1, Math.round(bytes / 1000)), { maximumFractionDigits: 0 })} KB`;
}

export default function FileRowItem({ row, now, onDeleted }: { row: FileRow; now: number; onDeleted: (id: string) => void }) {
  const t = useTranslations("my.files");
  const format = useFormatter();
  const hours = row.deleted ? null : hoursLeft(row.expiresAt, now);
  const status = row.deleted ? t("deleted") : hours === null ? t("deletesSoon") : t("deletesIn", { hours });
  const count = row.pages !== null ? t("pages", { count: row.pages }) : row.rows !== null ? t("rows", { count: row.rows }) : null;

  return (
    <li className={`${styles.fileRow} ${row.deleted ? styles.fileGone : ""}`}>
      <span className={`${styles.kind} ${kindColor[row.kind]}`}>{row.kind.toUpperCase()}</span>
      <span className={styles.fileName}>{row.name}</span>
      <span className={styles.fileFact}>{sizeLabel(row.size, (n, o) => format.number(n, o))}</span>
      {count ? <span className={styles.fileFact}>{count}</span> : null}
      <span className={`${styles.pill} ${row.deleted ? styles.pillGone : ""}`}>{status}</span>
      {row.deleted ? null : (
        <ConfirmDelete
          labels={{ delete: t("delete"), confirm: t("confirm"), cancel: t("cancel"), confirmDelete: t("confirmDelete"), deleting: t("deleting") }}
          run={() => deleteFile(row.id)}
          onDone={() => onDeleted(row.id)}
        />
      )}
    </li>
  );
}
