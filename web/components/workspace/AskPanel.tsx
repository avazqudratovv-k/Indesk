"use client";

import { useRef, useState, useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";
import DemoNotice from "@/components/ui/DemoNotice";
import { apiErrorKey, retryMinutes, ApiError } from "@/lib/api/errors";
import type { FileStatus } from "@/lib/run/live/submit";
import { MAX_CSV_ROWS, MAX_FILE_MB, MAX_PDF_CHARS, MAX_PDF_PAGES, MAX_QUESTION_CHARS } from "@/lib/limits";
import { MODE_SLOTS, questionLength, type SlotFile, type SlotId, type WorkspaceMode } from "@/lib/workspace/validate";
import Button from "@/components/ui/Button";
import AgentEndings from "./AgentEndings";
import ConsentBox from "./ConsentBox";
import FileSlot from "./FileSlot";
import ModeSwitch from "./ModeSwitch";
import QuestionBox from "./QuestionBox";
import SampleFile from "./SampleFile";
import { clearSampleDismissed, loadSampleFile, readSampleDismissed, SAMPLE_FILE_NAME, SAMPLE_ID, writeSampleDismissed } from "@/lib/workspace/sample";
import TeamReady from "./TeamReady";
import UploadInfo from "./UploadInfo";
import { useWorkspaceFiles } from "./use-workspace-files";
import styles from "./AskPanel.module.css";

// Nothing else writes the saved choice while the page is open, so there is nothing to subscribe to.
const subscribeNever = () => () => {};

export type RunSummary = { mode: WorkspaceMode; fileCount: number; question: string };

// What Run hands to the page: the summary plus the files themselves (the page uploads them).
export type RunSubmission = RunSummary & { files: SlotFile[] };

// The state of starting a real run (uploads, then the run request), owned by the page.
export type SubmitState = {
  stage: "idle" | "uploading" | "starting";
  progress: { done: number; total: number };
  fileStatus: Record<string, FileStatus>;
  failure: { code: ApiError["code"]; fileId: string | null; retryAfter?: number; rowLimit?: ApiError["rowLimit"] } | null;
  // A run of this person that is still going (found after RUN_ACTIVE): offered as "Watch it".
  activeRunId: string | null;
  // The run the Run tab already follows; the strip is not shown for it.
  followingRunId: string | null;
  onWatchActive: () => void;
  onFileRemoved: (fileId: string) => void;
  onDismissFailure: () => void;
};

type Need = "files" | "question" | "tooLong" | "consent";

// The Ask tab: mode switch, the two cards (files, question), the team strip and the upload info.
// Everything here is local state. Pressing Run hands the files to the page, which uploads them; nothing is uploaded before that.
// In Ask the Seoul sample is attached as a pending card: it becomes a File (and is uploaded) only when Run is pressed.
export default function AskPanel({ prefill = null, userId, freeLeft, plan, onRun, submit }: { prefill?: { text: string; n: number } | null; userId: string; freeLeft: number | null; plan: string; onRun: (submission: RunSubmission) => void; submit?: SubmitState }) {
  const t = useTranslations("workspace");
  // Check a document and Compare are shown but cannot be chosen yet (ModeSwitch), so this panel is always Ask.
  const mode: WorkspaceMode = "ask";
  const [question, setQuestion] = useState("");
  const [consent, setConsent] = useState(false);
  // A suggested question fills the Ask question box (the file stays attached); it never starts a run. Adjusted during render
  // when a new suggestion arrives, the React way of resetting state from a prop.
  const [seenPrefill, setSeenPrefill] = useState(0);
  if (prefill && prefill.n !== seenPrefill) {
    setSeenPrefill(prefill.n);
    setQuestion(prefill.text);
  }
  const [announcement, setAnnouncement] = useState("");
  const { slots, errors, add, remove } = useWorkspaceFiles(mode);
  // Whether the sample is on offer: off after the person removed it (kept per user) or chose a file of their own (this visit only).
  // The saved choice is read through useSyncExternalStore: while hydrating React uses the server snapshot (null), so the
  // first client render equals the server render (a hidden card of the same height), then switches to the browser value
  // before the next paint. Local changes (remove, own file, use sample) win over it, so it needs no subscription.
  const saved = useSyncExternalStore(
    subscribeNever,
    () => !readSampleDismissed(userId),
    () => null,
  );
  const [changed, setSampleOn] = useState<boolean | null>(null);
  const sampleOn = changed ?? saved;
  const [preparing, setPreparing] = useState(false);
  const [sampleFailed, setSampleFailed] = useState(false);
  const sampleFile = useRef<SlotFile | null>(null);
  const showActive = submit !== undefined && submit.activeRunId !== null && submit.failure?.code !== "RUN_ACTIVE" && submit.followingRunId !== submit.activeRunId;

  const trimmed = question.trim();
  const slotIds = MODE_SLOTS[mode];
  // sampleShown: the card takes its place (hidden while sampleOn is still null). sampleActive: it counts as the file to run.
  const sampleShown = sampleOn !== false && slots.files.length === 0;
  const sampleActive = sampleShown && sampleOn === true;
  const fileCount = slotIds.reduce((sum, id) => sum + slots[id].length, 0) + (sampleActive ? 1 : 0);

  function need(): Need | null {
    if (fileCount === 0) return "files";
    if (trimmed.length === 0) return "question";
    if (questionLength(question) > MAX_QUESTION_CHARS) return "tooLong";
    if (!consent) return "consent";
    return null;
  }

  const busy = (submit !== undefined && submit.stage !== "idle") || preparing;
  const missing = need();
  const busyHint = preparing ? t("sample.preparing") : submit && busy ? (submit.stage === "uploading" ? t("submit.uploading", { done: Math.min(submit.progress.done + 1, submit.progress.total), total: submit.progress.total }) : t("submit.starting")) : null;
  // freeLeft is null whenever GET /api/usage has not answered (or failed): then the hint names no number.
  const usesHint = plan === "free" && freeLeft !== null ? (freeLeft > 0 ? t("run.usesFree", { left: freeLeft }) : t("run.noFreeLeft")) : t("run.usesOther");
  const hint = busyHint ?? (missing ? t(`run.need.${missing}`) : usesHint);

  function handleAdd(slot: SlotId, files: File[]) {
    const result = add(slot, files);
    // A file of their own replaces the pending sample (nothing was uploaded for it, so nothing is lost).
    if (slot === "files" && result.added.length > 0 && sampleOn !== false) setSampleOn(false);
    const parts: string[] = [];
    if (result.added.length === 1) parts.push(t("upload.announceAddedOne", { name: result.added[0] }));
    else if (result.added.length > 1) parts.push(t("upload.announceAddedMany", { count: result.added.length }));
    if (result.rejected > 0) parts.push(t("upload.announceRejected", { count: result.rejected }));
    setAnnouncement(parts.join(" "));
  }

  function handleRemove(slot: SlotId, id: string) {
    if (busy) return;
    const item = slots[slot].find((entry) => entry.id === id);
    remove(slot, id);
    submit?.onFileRemoved(id);
    if (item) setAnnouncement(t("upload.announceRemoved", { name: item.file.name }));
  }

  function removeSample() {
    if (busy) return;
    setSampleOn(false);
    setSampleFailed(false);
    writeSampleDismissed(userId);
    submit?.onFileRemoved(SAMPLE_ID);
    setAnnouncement(t("sample.announceRemoved"));
  }

  function useSample() {
    if (busy) return;
    setSampleOn(true);
    clearSampleDismissed(userId);
    setAnnouncement(t("sample.announceAdded"));
  }

  async function run() {
    if (need() !== null || busy) return;
    const own = slotIds.flatMap((id) => slots[id]);
    if (!sampleActive) {
      onRun({ mode, fileCount, question: trimmed, files: own });
      return;
    }
    setSampleFailed(false);
    setPreparing(true);
    try {
      sampleFile.current ??= await loadSampleFile();
      onRun({ mode, fileCount, question: trimmed, files: [sampleFile.current] });
    } catch {
      setSampleFailed(true);
    } finally {
      setPreparing(false);
    }
  }

  const slot = (id: SlotId, extra: { csvOnly?: boolean } = {}) => (
    <FileSlot
      key={id}
      slot={id}
      csvOnly={extra.csvOnly}
      items={slots[id]}
      errors={errors[id]}
      statuses={submit?.fileStatus}
      locked={busy}
      onAdd={(files) => handleAdd(id, files)}
      onRemove={(fileId) => handleRemove(id, fileId)}
    />
  );

  return (
    <div className={styles.panel}>
      {showActive && submit ? (
        <div className={styles.problem} role="status">
          <span>{t("activeStrip")}</span>
          <Button size="sm" onClick={submit.onWatchActive}>{t("submit.watch")}</Button>
        </div>
      ) : null}

      <ModeSwitch mode={mode} />

      <section className={styles.cards}>
        <div className={styles.card}>
          <h2 className={styles.cardTitle}>{t("steps.askFiles")}</h2>
          {sampleShown ? (
            <div className={sampleOn === null ? styles.samplePending : undefined} aria-hidden={sampleOn === null || undefined} inert={sampleOn === null || undefined}>
              <SampleFile attached locked={busy} onRemove={removeSample} onUse={useSample} />
            </div>
          ) : null}
          {slot("files", { csvOnly: true })}
          {!sampleShown && slots.files.length === 0 ? <SampleFile attached={false} locked={busy} onRemove={removeSample} onUse={useSample} /> : null}
          <DemoNotice />
          <ConsentBox checked={consent} onChange={setConsent} />
        </div>

        <div className={styles.card}>
          <h2 className={styles.cardTitle}>{t("steps.askQuestion")}</h2>
          <QuestionBox
            value={question}
            onChange={setQuestion}
            placeholder={sampleShown ? t("question.placeholder") : t("question.placeholderOwn")}
            chips={sampleShown}
            chipsHidden={sampleOn === null}
          />
          <div className={styles.runBar}>
            <button type="button" className={styles.run} aria-disabled={missing !== null || busy} aria-describedby="ws-run-hint" onClick={run}>
              {t("run.ask")}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </button>
            <span id="ws-run-hint" className={styles.hint}>
              {hint}
            </span>
          </div>
          {sampleFailed ? (
            <div className={styles.problem} role="alert">
              <span>{t("sample.loadFailed")}</span>
            </div>
          ) : null}
          {submit?.failure ? <SubmitProblem submit={submit} failure={submit.failure} names={{ ...Object.fromEntries(slotIds.flatMap((id) => slots[id]).map((item) => [item.id, item.file.name])), [SAMPLE_ID]: SAMPLE_FILE_NAME }} /> : null}
        </div>
      </section>

      <p className={styles.srOnly} role="status">
        {announcement}
      </p>

      <TeamReady withHound={slots.files.some((item) => item.kind === "pdf")} />
      <AgentEndings />
      <UploadInfo />
    </div>
  );
}

// Why starting a run did not work: a generic message for the code (never server text), and for RUN_ACTIVE a way to
// watch the run that is already going. Announced politely; the Run button stays the place to try again.
function SubmitProblem({ submit, failure, names }: { submit: SubmitState; failure: NonNullable<SubmitState["failure"]>; names: Record<string, string> }) {
  const t = useTranslations("workspace");
  const tErrors = useTranslations("apiErrors");
  const error = new ApiError(0, failure.code, failure.retryAfter);
  const key = apiErrorKey(error);
  const limits = { mb: MAX_FILE_MB, pages: MAX_PDF_PAGES, chars: MAX_PDF_CHARS, rows: MAX_CSV_ROWS };
  const base = failure.code === "RATE_LIMITED" && failure.retryAfter !== undefined ? t("submit.tooSoon", { minutes: retryMinutes(error) }) : tErrors(key, limits);
  const name = failure.fileId ? names[failure.fileId] : undefined;
  // The server's counts, not a number of ours: without them (or without a file name) the generic line is used.
  const text = failure.code === "RUN_ACTIVE" ? (submit.activeRunId ? t("submit.activeRunWatch") : t("submit.activeRun")) : failure.code === "TOO_MANY_ROWS" && name && failure.rowLimit ? tErrors("TOO_MANY_ROWS_DETAIL", { name, rows: failure.rowLimit.rows, max: failure.rowLimit.max }) : name ? t("submit.fileError", { name, message: base }) : base;
  return (
    <div className={styles.problem} role="alert">
      <span>{text}</span>
      {failure.code === "RUN_ACTIVE" && submit.activeRunId ? <Button size="sm" onClick={submit.onWatchActive}>{t("submit.watch")}</Button> : null}
    </div>
  );
}
