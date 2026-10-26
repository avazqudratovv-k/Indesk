"use client";

import { useTranslations } from "next-intl";
import type { EvidenceView } from "@/lib/report/view";
import ScrollRegion from "./ScrollRegion";
import styles from "./EvidencePanel.module.css";

const kindColor: Record<string, string> = {
  table: "var(--c-bea)",
  chart: "var(--c-bea)",
  code: "var(--c-bea)",
  diff: "var(--c-bea)",
  image_boxes: "var(--c-cham)",
  passage: "var(--c-hou)",
  critic_note: "var(--c-cat)",
};

// The evidence behind a claim: kind, title, text, then whatever the payload holds (code, rows, quote) and the source line.
// `aside` is the board's right-hand panel (desktop); `inline` opens under a claim on phones (not on the board, DECISIONS).
export default function EvidencePanel({ view, variant }: { view: EvidenceView | null; variant: "aside" | "inline" }) {
  const t = useTranslations("report.evidence");
  const root = variant === "aside" ? styles.aside : styles.inline;
  if (!view) {
    return (
      <aside className={root} aria-label={t("title")}>
        <div className={styles.eyebrow}>{t("title")}</div>
        <p className={styles.body}>{t("empty")}</p>
      </aside>
    );
  }
  const defaultSource = view.location ? t("source", { file: view.fileName, location: view.location }) : t("sourceFile", { file: view.fileName });
  const { table } = view;
  const source = view.metaText !== undefined ? view.metaText : view.tool ? `${view.tool} · ${defaultSource}` : defaultSource;
  return (
    <aside key={view.ref} className={root} aria-label={t("title")}>
      <div className={styles.eyebrow}>{t("title")}</div>
      <div>
        <span className={styles.kind} style={{ "--kind": kindColor[view.type] ?? "var(--accent)" } as React.CSSProperties}>
          {t(`kind.${view.type}`)}
        </span>
        <h2 className={styles.title}>{view.title}</h2>
      </div>
      {view.body ? <p className={styles.body}>{view.body}</p> : null}
      {view.code ? (
        <ScrollRegion label={view.title} className={styles.code}>
          <pre className={styles.pre}>{view.code}</pre>
        </ScrollRegion>
      ) : null}
      {table ? (
        <ScrollRegion label={view.title} className={styles.tableBox}>
          <table className={styles.table}>
            <thead>
              <tr>
                {table.headers.map((header, index) => (
                  <th key={index} scope="col">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, index) => (
                    <td key={index} className={index === 0 ? undefined : styles.num}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
      ) : null}
      {view.quote ? <blockquote className={styles.quote}>{view.quote}</blockquote> : null}
      {source ? <div className={styles.meta}>{source}</div> : null}
    </aside>
  );
}
