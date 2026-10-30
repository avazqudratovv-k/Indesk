"use client";

import { useEffect, useId, useRef, useState, type DragEvent } from "react";
import { useFormatter, useTranslations } from "next-intl";
import type { FileStatus } from "@/lib/run/live/submit";
import { ACCEPT_ATTRIBUTE, ASK_ACCEPT, extensionOf, formatSize, MAX_FILE_BYTES, SLOT_MAX, type FileError, type SlotFile, type SlotId } from "@/lib/workspace/validate";
import styles from "./FileSlot.module.css";

type Props = {
  slot: SlotId;
  title?: string;
  items: SlotFile[];
  errors: FileError[];
  documentOnly?: boolean;
  csvOnly?: boolean;
  // Real upload state per file id (Ask runs), and whether the list may change right now (uploads in progress).
  statuses?: Record<string, FileStatus>;
  locked?: boolean;
  onAdd: (files: File[]) => void;
  onRemove: (id: string) => void;
};

const kindColor = { csv: "var(--c-cham)", pdf: "var(--c-cat)", image: "var(--c-bea)" } as const;

// One upload area with its list of added files. Single-file slots (document, file A, file B) swap the drop area
// for the file once it is added. Files stay in the browser: this component never reads their contents.
export default function FileSlot({ slot, title, items, errors, documentOnly, csvOnly, statuses, locked, onAdd, onRemove }: Props) {
  const t = useTranslations("workspace");
  const format = useFormatter();
  const ids = useId();
  const titleId = `${ids}-title`;
  const helpId = `${ids}-help`;
  const dropId = `${ids}-drop`;
  const single = SLOT_MAX[slot] === 1;
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const removeButtons = useRef(new Map<string, HTMLButtonElement>());
  // Where focus goes after the list changes: "next" after a removal (index to land on), "file" after adding to a single slot.
  const pending = useRef<{ type: "remove"; index: number } | { type: "add" } | null>(null);
  const mb = MAX_FILE_BYTES / (1024 * 1024);

  useEffect(() => {
    const action = pending.current;
    if (!action) return;
    pending.current = null;
    if (action.type === "add") {
      const first = items[0];
      if (first) removeButtons.current.get(first.id)?.focus();
      return;
    }
    const target = items[Math.min(action.index, items.length - 1)];
    if (target) removeButtons.current.get(target.id)?.focus();
    else input.current?.focus();
  }, [items]);

  function handle(files: File[]) {
    if (files.length === 0) return;
    if (single) pending.current = { type: "add" };
    onAdd(files);
  }

  function onDrag(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    if (event.type === "dragleave" && event.currentTarget.contains(event.relatedTarget as Node | null)) return;
    setDragging(event.type !== "dragleave");
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    handle(Array.from(event.dataTransfer.files));
  }

  const showDrop = (!single || items.length === 0) && !locked;

  // Neutral note after a PDF upload; nothing for a CSV (field absent) or when every page has text (0).
  function noteText(status: FileStatus | undefined): string {
    return status?.state === "ready" && status.pagesWithoutText !== undefined && status.pagesWithoutText > 0 ? t("upload.pagesWithoutText", { n: status.pagesWithoutText }) : "";
  }

  function statusText(status: FileStatus | undefined): string {
    if (!status) return "";
    if (status.state === "ready") return status.expiresAt ? t("upload.statusReady", { when: format.dateTime(status.expiresAt, { dateStyle: "medium", timeStyle: "short" }) }) : "";
    return t(`upload.status.${status.state}`);
  }

  return (
    <div className={styles.slot}>
      {title ? (
        <h3 id={titleId} className={styles.title}>
          {title}
        </h3>
      ) : null}

      {items.length > 0 ? (
        <ul className={styles.list} aria-label={t("upload.listLabel")}>
          {items.map((item, index) => {
            const size = formatSize(item.file.size);
            return (
              <li key={item.id} className={styles.row}>
                <span className={styles.kind} style={{ background: kindColor[item.kind] }} aria-hidden="true">
                  {extensionOf(item.file.name).toUpperCase()}
                </span>
                <span className={styles.info}>
                  <span className={styles.name}>{item.file.name}</span>
                  <span className={styles.meta}>
                    {format.number(size.value)} {size.unit}
                    {statusText(statuses?.[item.id]) ? ` · ${statusText(statuses?.[item.id])}` : ""}
                  </span>
                  {noteText(statuses?.[item.id]) ? <span className={styles.meta}>{noteText(statuses?.[item.id])}</span> : null}
                </span>
                <button
                  type="button"
                  className={styles.remove}
                  aria-label={t("upload.remove", { name: item.file.name })}
                  disabled={locked}
                  ref={(node) => {
                    if (node) removeButtons.current.set(item.id, node);
                    else removeButtons.current.delete(item.id);
                  }}
                  onClick={() => {
                    pending.current = { type: "remove", index };
                    onRemove(item.id);
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                    <path d="M6 6l12 12M18 6L6 18" />
                  </svg>
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}

      {showDrop ? (
        <label
          className={styles.drop}
          data-dragging={dragging || undefined}
          onDragEnter={onDrag}
          onDragOver={onDrag}
          onDragLeave={onDrag}
          onDrop={onDrop}
        >
          <input
            ref={input}
            id={dropId}
            className={styles.input}
            type="file"
            multiple={!single}
            accept={documentOnly ? ".pdf,application/pdf" : csvOnly ? ASK_ACCEPT : ACCEPT_ATTRIBUTE}
            aria-labelledby={`${dropId}-label`}
            aria-describedby={helpId}
            onChange={(event) => {
              handle(Array.from(event.currentTarget.files ?? []));
              // Lets the same file be picked again after it was removed.
              event.currentTarget.value = "";
            }}
          />
          <svg className={styles.dropIcon} width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M12 16V5M7 10l5-5 5 5" />
            <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
          </svg>
          <span id={`${dropId}-label`} className={styles.dropTitle}>
            {t("upload.dropOne")}
          </span>
          <span id={helpId} className={styles.help}>
            {documentOnly ? t("upload.helpDocument", { mb }) : t("upload.help", { mb })}
          </span>
          <span className={styles.choose} aria-hidden="true">
            {t("upload.choose")}
          </span>
        </label>
      ) : null}

      <div className={styles.errors} aria-live="polite">
        {errors.map((error, index) => (
          <p key={`${error.name}-${index}`} className={styles.error}>
            <svg className={styles.errorIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
              <circle cx="12" cy="12" r="9" />
              <path d="M12 7.5v5.5M12 16.5v.1" />
            </svg>
            <span>{t(error.code === "slotFull" && slot === "files" ? "errors.askOneFile" : `errors.${error.code}`, { name: error.name, mb, max: SLOT_MAX[slot] })}</span>
          </p>
        ))}
      </div>
    </div>
  );
}
