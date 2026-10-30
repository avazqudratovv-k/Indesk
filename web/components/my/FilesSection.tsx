"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { loadFiles, type FileRow } from "@/lib/my/api";
import FileRowItem from "./FileRowItem";
import styles from "./my.module.css";

type State = { status: "loading" } | { status: "error" } | { status: "ready"; items: FileRow[]; now: number };

export default function FilesSection() {
  const t = useTranslations("my");
  const tCommon = useTranslations("common");
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    loadFiles(controller.signal).then(
      (items) => setState({ status: "ready", items, now: Date.now() }),
      () => {
        if (!controller.signal.aborted) setState({ status: "error" });
      },
    );
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => {
    setState({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  // A deleted file stays in the list as a muted "Deleted" row, the same as the server shows it with include_deleted.
  function markDeleted(id: string) {
    setState((current) =>
      current.status === "ready" ? { ...current, items: current.items.map((row) => (row.id === id ? { ...row, deleted: true } : row)) } : current,
    );
  }

  return (
    <section className={styles.section} aria-labelledby="my-files-title" aria-busy={state.status === "loading"}>
      <h2 id="my-files-title" className={styles.sectionTitle}>
        {t("files.title")}
      </h2>
      <p className={styles.help}>{t("files.note")}</p>
      <p className={styles.help}>{t("files.deleteNote")}</p>

      {state.status === "loading" ? (
        <p className={styles.state} role="status">
          {tCommon("loading")}
        </p>
      ) : state.status === "error" ? (
        <div className={styles.errorCard} role="alert">
          <p>{t("loadError")}</p>
          <Button size="sm" onClick={retry}>
            {t("retry")}
          </Button>
        </div>
      ) : state.items.length === 0 ? (
        <p className={styles.empty}>{t("files.empty")}</p>
      ) : (
        <ul className={styles.fileList}>
          {state.items.map((row) => (
            <FileRowItem key={row.id} row={row} now={state.now} onDeleted={markDeleted} />
          ))}
        </ul>
      )}
    </section>
  );
}
