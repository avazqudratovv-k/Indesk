import type { LiveDone, LiveStep, RunSnapshot, RunStatus } from "./types";

// What the screen knows about one run. Steps are kept sorted by `seq` and unique; the stream may replay old events
// (a reconnect without Last-Event-ID, a reload) and the reducer simply ignores what it already has.
export type LiveRun = {
  id: string;
  question: string;
  status: RunStatus;
  steps: LiveStep[];
  done: LiveDone | null;
  createdAt: number | null;
  startedAt: number | null;
  finishedAt: number | null;
};

export type LiveAction =
  | { type: "start"; id: string; question: string; status: RunStatus; now: number }
  | { type: "seed"; snapshot: RunSnapshot }
  | { type: "step"; step: LiveStep; now: number }
  | { type: "done"; done: LiveDone; now: number }
  | { type: "clear" };

export function initialRun(id: string, question: string, status: RunStatus = "queued", now: number | null = null): LiveRun {
  return { id, question, status, steps: [], done: null, createdAt: now, startedAt: null, finishedAt: null };
}

function insertStep(steps: LiveStep[], step: LiveStep): LiveStep[] {
  if (steps.some((existing) => existing.seq === step.seq)) return steps;
  const next = [...steps, step];
  next.sort((a, b) => a.seq - b.seq);
  return next;
}

export function lastSeq(run: LiveRun): number {
  return run.steps.length > 0 ? run.steps[run.steps.length - 1].seq : 0;
}

export function liveReducer(state: LiveRun | null, action: LiveAction): LiveRun | null {
  switch (action.type) {
    case "clear":
      return null;
    case "start":
      return initialRun(action.id, action.question, action.status, action.now);
    case "seed": {
      const { snapshot } = action;
      if (state && state.id !== snapshot.id) return state; // a late answer for a run we left
      let steps = state?.steps ?? [];
      for (const step of snapshot.steps) steps = insertStep(steps, step);
      const done: LiveDone | null = snapshot.status === "finished" ? { outcome: snapshot.outcome ?? "failed", reason: snapshot.reason, reportId: snapshot.reportId } : (state?.done ?? null);
      return {
        id: snapshot.id,
        question: snapshot.question || state?.question || "",
        status: done ? "finished" : snapshot.status,
        steps,
        done,
        createdAt: snapshot.createdAt ?? state?.createdAt ?? null,
        startedAt: snapshot.startedAt ?? state?.startedAt ?? null,
        finishedAt: snapshot.finishedAt ?? state?.finishedAt ?? null,
      };
    }
    case "step": {
      if (!state) return state;
      const steps = insertStep(state.steps, action.step);
      if (steps === state.steps) return state;
      return { ...state, steps, status: state.done ? "finished" : "running", startedAt: state.startedAt ?? action.now };
    }
    case "done": {
      if (!state || state.done) return state;
      return { ...state, done: action.done, status: "finished", finishedAt: state.finishedAt ?? action.now };
    }
  }
}
