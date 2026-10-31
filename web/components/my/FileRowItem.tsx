"use client";

import { useFormatter, useTranslations } from "next-intl";
import { deleteFile, hoursLeft, type FileRow } from "@/lib/my/api";
import { formatSize } from "@/lib/workspace/validate";
import ConfirmDelete from "./ConfirmDelete";
import styles from "./my.module.css";

const kindColor: Record<FileRow["kind"], string> = {
  csv: styles.kindCsv,
  pdf: styles.kindPdf,
  jpg: styles.kindImage,
  png: styles.kindImage,
  txt: styles.kindText,
};

export default function FileRowItem({ row, now, onDeleted }: { row: FileRow; now: number; onDeleted: (id: string) => void }) {
  const t = useTranslations("my.files");
  const format = useFormatter();
  const hours = row.deleted ? null : hoursLeft(row.expiresAt, now);
  const status = row.deleted ? t("deleted") : hours === null ? t("deletesSoon") : t("deletesIn", { hours });
  // The workspace's formatter, so one file shows one size everywhere.
  const size = formatSize(row.size);
  const count = row.pages !== null ? t("pages", { count: row.pages }) : row.rows !== null ? t("rows", { count: row.rows }) : null;

  return (
    <li className={`${styles.fileRow} ${row.deleted ? styles.fileGone : ""}`}>
      <span className={`${styles.kind} ${kindColor[row.kind]}`}>{row.kind.toUpperCase()}</span>
      <span className={styles.fileName} title={row.name}>
        {row.name}
      </span>
      <span className={styles.fileFact}>{`${format.number(size.value)} ${size.unit}`}</span>
      {/* Always rendered, even empty, so the columns of the desktop grid line up (hidden on phones when empty). */}
      <span className={styles.fileFact}>{count}</span>
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
