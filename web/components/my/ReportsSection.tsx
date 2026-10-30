"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import Button from "@/components/ui/Button";
import { loadReports, type ReportRow } from "@/lib/my/api";
import ReportRowItem from "./ReportRowItem";
import styles from "./my.module.css";

type State = { status: "loading" } | { status: "error" } | { status: "ready"; items: ReportRow[]; next: string | null; more: "idle" | "loading" | "error" };

export default function ReportsSection() {
  const t = useTranslations("my");
  const tCommon = useTranslations("common");
  const [state, setState] = useState<State>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    loadReports(null, controller.signal).then(
      (page) => setState({ status: "ready", items: page.items, next: page.nextCursor, more: "idle" }),
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

  async function loadMore() {
    if (state.status !== "ready" || !state.next) return;
    const { items, next } = state;
    setState({ status: "ready", items, next, more: "loading" });
    try {
      const page = await loadReports(next);
      // A report can come back on a later page after a delete moved the list; the id is the key, so keep the first.
      const seen = new Set(items.map((row) => row.id));
      setState({ status: "ready", items: [...items, ...page.items.filter((row) => !seen.has(row.id))], next: page.nextCursor, more: "idle" });
    } catch {
      setState({ status: "ready", items, next, more: "error" });
    }
  }

  function removeRow(id: string) {
    setState((current) => (current.status === "ready" ? { ...current, items: current.items.filter((row) => row.id !== id) } : current));
  }

  return (
    <section className={styles.section} aria-labelledby="my-reports-title" aria-busy={state.status === "loading"}>
      <h2 id="my-reports-title" className={styles.sectionTitle}>
        {t("reports.title")}
      </h2>
      <p className={styles.help}>{t("reports.private")}</p>
      <p className={styles.help}>{t("reports.deleteNote")}</p>

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
      ) : state.items.length === 0 && !state.next ? (
        <p className={styles.empty}>{t("reports.empty")}</p>
      ) : (
        <>
          <ul className={styles.list}>
            {state.items.map((row) => (
              <ReportRowItem key={row.id} row={row} onDeleted={removeRow} />
            ))}
          </ul>
          {state.more === "error" ? (
            <p className={styles.rowError} role="alert">
              {t("loadError")}
            </p>
          ) : null}
          {state.next ? (
            <Button className={styles.more} onClick={loadMore} disabled={state.more === "loading"}>
              {state.more === "loading" ? tCommon("loading") : t("loadMore")}
            </Button>
          ) : null}
        </>
      )}
    </section>
  );
}
