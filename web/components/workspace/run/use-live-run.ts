"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { ApiError } from "@/lib/api/errors";
import { createRun, getActiveRun, getRun, uploadCsv } from "@/lib/run/live/api";
import { liveReducer, type LiveRun } from "@/lib/run/live/reducer";
import { clearRunId, readRunId, writeRunId } from "@/lib/run/live/storage";
import { SubmitError, submitRun, type FileStatus, type SubmitFile } from "@/lib/run/live/submit";
import type { UploadedFile } from "@/lib/run/live/types";
import { browserWatchDeps, watchRun } from "@/lib/run/live/watch";

export type Connection = "live" | "lost" | "signedOut";
export type SubmitStage = "idle" | "uploading" | "starting";
export type SubmitFailure = { code: SubmitError["code"]; fileId: string | null; retryAfter?: number };

// The real run of the Ask tab: starting it (uploads, then POST /api/runs), following it over the event stream, and
// finding it again after a reload or in another tab. The run id is the only thing kept in localStorage.
export function useLiveRun(userId: string | null) {
  const [run, dispatch] = useReducer(liveReducer, null);
  const [connection, setConnection] = useState<Connection>("live");
  const [attempt, setAttempt] = useState(0);
  const [stage, setStage] = useState<SubmitStage>("idle");
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [fileStatus, setFileStatus] = useState<Record<string, FileStatus>>({});
  const [failure, setFailure] = useState<SubmitFailure | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const uploaded = useRef(new Map<string, UploadedFile>());
  const busy = useRef(false);

  const runId = run?.id ?? null;
  const following = run !== null && run.done === null;

  // Find the person's latest run again (reload, or another tab started it).
  useEffect(() => {
    if (!userId) return;
    const stored = readRunId(userId);
    if (!stored) return;
    let live = true;
    getRun(stored).then(
      (snapshot) => {
        if (live) dispatch({ type: "seed", snapshot });
      },
      (error: unknown) => {
        if (live && error instanceof ApiError && error.code === "NOT_FOUND") clearRunId(userId);
      },
    );
    return () => {
      live = false;
    };
  }, [userId]);

  // A run of this person that is still going, found once on load (another tab or browser may have started it). No polling.
  useEffect(() => {
    if (!userId) return;
    const controller = new AbortController();
    getActiveRun(controller.signal).then(
      (snapshot) => {
        if (!controller.signal.aborted && snapshot && snapshot.status !== "finished") setActiveRunId(snapshot.id);
      },
      () => {}, // no strip when the lookup fails; Run still reports RUN_ACTIVE if it applies
    );
    return () => controller.abort();
  }, [userId]);

  // Follow an unfinished run. `attempt` changes when the person presses Reconnect.
  useEffect(() => {
    if (!runId || !following) return;
    const watcher = watchRun(
      runId,
      {
        onStep: (step) => dispatch({ type: "step", step, now: Date.now() }),
        onDone: (done) => dispatch({ type: "done", done, now: Date.now() }),
        onSnapshot: (snapshot) => dispatch({ type: "seed", snapshot }),
        onGone: () => {
          if (userId) clearRunId(userId);
          dispatch({ type: "clear" });
        },
        onLost: ({ signedOut }) => setConnection(signedOut ? "signedOut" : "lost"),
      },
      browserWatchDeps((id) => getRun(id)),
    );
    return () => watcher.close();
  }, [runId, following, attempt, userId]);

  const start = useCallback(
    async (files: readonly SubmitFile[], question: string): Promise<boolean> => {
      if (!userId || busy.current) return false;
      busy.current = true;
      setFailure(null);
      setActiveRunId(null);
      setConnection("live");
      setStage("uploading");
      try {
        const { runId: id } = await submitRun(
          { files, question, uploaded: uploaded.current, onStatus: (fileId, status) => setFileStatus((all) => ({ ...all, [fileId]: status })), onProgress: (done, total) => setProgress({ done, total }) },
          { upload: (file) => uploadCsv(file), create: createRun, newKey: () => crypto.randomUUID(), now: Date.now },
        );
        writeRunId(userId, id);
        dispatch({ type: "start", id, question: question.trim(), status: "queued", now: Date.now() });
        setFileStatus({});
        return true;
      } catch (error) {
        const failed = error instanceof SubmitError ? error : new SubmitError("UNKNOWN", null);
        setFailure({ code: failed.code, fileId: failed.fileId, retryAfter: failed.retryAfter });
        if (failed.code === "RUN_ACTIVE") {
          // The error names the run in the way; only if it does not, ask once which run is active.
          if (failed.runId) setActiveRunId(failed.runId);
          else getActiveRun().then((snapshot) => setActiveRunId(snapshot && snapshot.status !== "finished" ? snapshot.id : null), () => {});
        }
        return false;
      } finally {
        busy.current = false;
        setStage("idle");
      }
    },
    [userId],
  );

  // "Watch it": open the run that RUN_ACTIVE told us about.
  const watchActive = useCallback(async () => {
    if (!activeRunId) return;
    try {
      const snapshot = await getRun(activeRunId);
      dispatch({ type: "seed", snapshot });
      if (userId) writeRunId(userId, snapshot.id);
      setFailure(null);
      setActiveRunId(null);
    } catch {
      setActiveRunId(null);
    }
  }, [activeRunId, userId]);

  const reconnect = useCallback(() => {
    setConnection("live");
    setAttempt((value) => value + 1);
  }, []);

  // Back to the Ask tab for a new question. The finished run stays reachable by reload until a new run replaces it.
  const forgetFile = useCallback((fileId: string) => {
    uploaded.current.delete(fileId);
    setFileStatus((all) => Object.fromEntries(Object.entries(all).filter(([id]) => id !== fileId)));
  }, []);

  const clearFailure = useCallback(() => {
    setFailure(null);
    setActiveRunId(null);
  }, []);

  return { run: run satisfies LiveRun | null, connection, stage, progress, fileStatus, failure, activeRunId, start, watchActive, reconnect, forgetFile, clearFailure };
}

export type LiveRunApi = ReturnType<typeof useLiveRun>;
