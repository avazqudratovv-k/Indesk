"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import DemoNotice from "@/components/ui/DemoNotice";
import { MAX_QUESTION_CHARS, MODE_SLOTS, questionLength, type SlotId, type WorkspaceMode } from "@/lib/workspace/validate";
import ConsentBox from "./ConsentBox";
import FileSlot from "./FileSlot";
import ModeSwitch from "./ModeSwitch";
import QuestionBox from "./QuestionBox";
import TeamReady from "./TeamReady";
import UploadInfo from "./UploadInfo";
import { useWorkspaceFiles } from "./use-workspace-files";
import styles from "./AskPanel.module.css";

export type RunSummary = { mode: WorkspaceMode; fileCount: number; question: string };

type Need = "files" | "document" | "sources" | "both" | "question" | "tooLong" | "consent";

// The Ask tab: mode switch, the two cards (files, question), the team strip and the upload info.
// Everything here is local state. Pressing Run hands a summary to the page; nothing is uploaded or stored.
export default function AskPanel({ freeRuns, plan, onRun }: { freeRuns: number | null; plan: string; onRun: (summary: RunSummary) => void }) {
  const t = useTranslations("workspace");
  const [mode, setMode] = useState<WorkspaceMode>("ask");
  const [questions, setQuestions] = useState<Record<WorkspaceMode, string>>({ ask: "", check: "", compare: "" });
  const [consent, setConsent] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const { slots, errors, add, remove } = useWorkspaceFiles(mode);

  const question = questions[mode];
  const trimmed = question.trim();
  const slotIds = MODE_SLOTS[mode];
  const fileCount = slotIds.reduce((sum, id) => sum + slots[id].length, 0);

  function need(): Need | null {
    if (mode === "ask") {
      if (fileCount === 0) return "files";
      if (trimmed.length === 0) return "question";
    }
    if (mode === "check") {
      if (slots.document.length === 0) return "document";
      if (slots.sources.length === 0) return "sources";
    }
    if (mode === "compare" && (slots.fileA.length === 0 || slots.fileB.length === 0)) return "both";
    if (questionLength(question) > MAX_QUESTION_CHARS) return "tooLong";
    if (!consent) return "consent";
    return null;
  }

  const missing = need();
  const hint = missing ? t(`run.need.${missing}`) : plan === "free" && freeRuns !== null ? t("run.usesFree", { runs: freeRuns }) : t("run.usesOther");

  function handleAdd(slot: SlotId, files: File[]) {
    const result = add(slot, files);
    const parts: string[] = [];
    if (result.added.length === 1) parts.push(t("upload.announceAddedOne", { name: result.added[0] }));
    else if (result.added.length > 1) parts.push(t("upload.announceAddedMany", { count: result.added.length }));
    if (result.rejected > 0) parts.push(t("upload.announceRejected", { count: result.rejected }));
    setAnnouncement(parts.join(" "));
  }

  function handleRemove(slot: SlotId, id: string) {
    const item = slots[slot].find((entry) => entry.id === id);
    remove(slot, id);
    if (item) setAnnouncement(t("upload.announceRemoved", { name: item.file.name }));
  }

  function run() {
    if (need() !== null) return;
    onRun({ mode, fileCount, question: trimmed });
  }

  const slot = (id: SlotId, extra: { title?: string; documentOnly?: boolean } = {}) => (
    <FileSlot
      key={id}
      slot={id}
      title={extra.title}
      documentOnly={extra.documentOnly}
      items={slots[id]}
      errors={errors[id]}
      onAdd={(files) => handleAdd(id, files)}
      onRemove={(fileId) => handleRemove(id, fileId)}
    />
  );

  const stepFiles = mode === "ask" ? "steps.askFiles" : mode === "check" ? "steps.checkFiles" : "steps.compareFiles";
  const stepTwo = mode === "ask" ? "steps.askQuestion" : mode === "check" ? "steps.checkNext" : "steps.compareFocus";
  const checkSteps = t.raw("checkSteps") as string[];

  return (
    <div className={styles.panel}>
      <ModeSwitch mode={mode} onChange={setMode} />

      <section className={styles.cards}>
        <div className={styles.card}>
          <h2 className={styles.cardTitle}>{t(stepFiles)}</h2>
          {mode === "ask" ? slot("files") : null}
          {mode === "check" ? (
            <>
              {slot("document", { title: t("slots.document"), documentOnly: true })}
              {slot("sources", { title: t("slots.sources") })}
            </>
          ) : null}
          {mode === "compare" ? (
            <>
              {slot("fileA", { title: t("slots.fileA") })}
              {slot("fileB", { title: t("slots.fileB") })}
            </>
          ) : null}
          <DemoNotice />
          <ConsentBox checked={consent} onChange={setConsent} />
        </div>

        <div className={styles.card}>
          <h2 className={styles.cardTitle}>{t(stepTwo)}</h2>
          {mode === "check" ? (
            <ol className={styles.steps}>
              {checkSteps.map((text, index) => (
                <li key={text} className={styles.step}>
                  <span className={styles.stepNumber}>{index + 1}</span>
                  <span>{text}</span>
                </li>
              ))}
            </ol>
          ) : (
            <QuestionBox
              key={mode}
              value={question}
              onChange={(value) => setQuestions((all) => ({ ...all, [mode]: value }))}
              placeholder={mode === "ask" ? t("question.placeholder") : t("question.focusPlaceholder")}
              chips={mode === "ask"}
            />
          )}
          <div className={styles.runBar}>
            <button type="button" className={styles.run} aria-disabled={missing !== null} aria-describedby="ws-run-hint" onClick={run}>
              {t(`run.${mode}`)}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </button>
            <span id="ws-run-hint" className={styles.hint}>
              {hint}
            </span>
          </div>
        </div>
      </section>

      <p className={styles.srOnly} role="status">
        {announcement}
      </p>

      <TeamReady />
      <UploadInfo />
    </div>
  );
}
