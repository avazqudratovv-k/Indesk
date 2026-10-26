import { ApiError, errorFromResponse } from "@/lib/api/errors";
import { parseDone, parseStep } from "./parse";
import type { LiveDone, LiveStep, RunSnapshot } from "./types";

// Follows one run over Server-Sent Events.
//
// EventSource cannot show an HTTP status. So when it fails we do not guess: we ask GET /api/runs/{id}, which tells the
// truth (finished, still running, gone, not signed in). The browser's own reconnect (which sends Last-Event-ID) is left
// alone while the connection is merely dropping; we step in after repeated failures, or at once when it gives up.
// The number of reopenings is capped, so a broken server can never cause a loop.

export type SourceLike = {
  readonly readyState: number;
  addEventListener: (type: string, listener: (event: MessageEvent | Event) => void) => void;
  close: () => void;
};

export type WatchDeps = {
  createSource: (url: string) => SourceLike;
  getRun: (id: string) => Promise<RunSnapshot>;
  setTimer: (callback: () => void, ms: number) => unknown;
  clearTimer: (handle: unknown) => void;
  // Asks the events URL once for its HTTP status (EventSource hides it). True when the server refused because this
  // person already follows too many runs (TOO_MANY_STREAMS). Optional: without it the cause stays unknown.
  probeStreamLimit?: (runId: string) => Promise<boolean>;
  // Waits before reopening after the Nth failure (index 0 is the first). Its length is the cap on reopenings.
  backoffMs: readonly number[];
};

export type WatchHandlers = {
  onStep: (step: LiveStep) => void;
  onDone: (done: LiveDone) => void;
  // Facts from GET /api/runs/{id}: replace what we know (steps are deduplicated by the reducer).
  onSnapshot: (snapshot: RunSnapshot) => void;
  // The run is not ours or not there any more.
  onGone: () => void;
  // The stream could not be kept; `signedOut` is true when the server said the session is over.
  onLost: (why: { signedOut: boolean; tooManyStreams?: boolean }) => void;
};

export type Watcher = { close: () => void };

const CONNECTING = 0;
const CLOSED = 2;
// Consecutive failures with no successful open before we stop trusting the browser's own reconnect.
const FAILURES_BEFORE_CHECK = 2;

// One stream per run in this tab: starting a second watcher for the same run closes the first (React StrictMode runs
// effects twice in development, and a stray double effect must never leave two connections open).
const active = new Map<string, Watcher>();

export function watchRun(runId: string, handlers: WatchHandlers, deps: WatchDeps): Watcher {
  active.get(runId)?.close();

  let closed = false;
  let source: SourceLike | null = null;
  let timer: unknown = null;
  let failures = 0;
  let reopenings = 0;

  function stopSource() {
    source?.close();
    source = null;
  }

  function finish() {
    closed = true;
    stopSource();
    if (timer !== null) deps.clearTimer(timer);
    timer = null;
    if (active.get(runId) === watcher) active.delete(runId);
  }

  function lost(signedOut: boolean) {
    finish();
    handlers.onLost({ signedOut });
  }

  async function check() {
    stopSource();
    try {
      const snapshot = await deps.getRun(runId);
      if (closed) return;
      handlers.onSnapshot(snapshot);
      if (snapshot.status === "finished") {
        finish();
        handlers.onDone({ outcome: snapshot.outcome ?? "failed", reason: snapshot.reason, reportId: snapshot.reportId });
        return;
      }
    } catch (error) {
      if (closed) return;
      if (error instanceof ApiError && error.code === "UNAUTHENTICATED") return lost(true);
      if (error instanceof ApiError && error.code === "NOT_FOUND") {
        finish();
        handlers.onGone();
        return;
      }
      // Network or server trouble: treated like a still-running run that we could not reach.
    }
    if (deps.probeStreamLimit && (await deps.probeStreamLimit(runId).catch(() => false))) {
      if (closed) return;
      finish();
      handlers.onLost({ signedOut: false, tooManyStreams: true });
      return;
    }
    if (closed) return;
    if (reopenings >= deps.backoffMs.length) return lost(false);
    const wait = deps.backoffMs[reopenings];
    reopenings += 1;
    timer = deps.setTimer(() => {
      timer = null;
      if (!closed) open();
    }, wait);
  }

  function open() {
    stopSource();
    const next = deps.createSource(`/api/runs/${encodeURIComponent(runId)}/events`);
    source = next;
    next.addEventListener("open", () => {
      if (closed || source !== next) return;
      failures = 0;
    });
    next.addEventListener("step", (event) => {
      if (closed || source !== next) return;
      failures = 0;
      const step = parseStep(parseJson((event as MessageEvent).data));
      if (step) handlers.onStep(step);
    });
    next.addEventListener("done", (event) => {
      if (closed || source !== next) return;
      const done = parseDone(parseJson((event as MessageEvent).data));
      finish();
      if (done) handlers.onDone(done);
      else handlers.onDone({ outcome: "failed", reason: null, reportId: null }); // an unreadable end is never shown as success
    });
    next.addEventListener("error", () => {
      if (closed || source !== next) return;
      failures += 1;
      // CLOSED: the browser gave up (an HTTP error, or the 204 for a run that is already over).
      // CONNECTING: it is retrying by itself; give it a couple of tries first.
      if (next.readyState === CLOSED || (next.readyState === CONNECTING && failures >= FAILURES_BEFORE_CHECK)) void check();
    });
  }

  const watcher: Watcher = { close: finish };
  active.set(runId, watcher);
  open();
  return watcher;
}

function parseJson(data: unknown): unknown {
  if (typeof data !== "string") return null;
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

export const defaultBackoffMs: readonly number[] = [1000, 2000, 4000, 8000, 15000];

// One request to the events URL, read only for its status; an accepted stream is closed at once.
async function probeStreamLimit(runId: string): Promise<boolean> {
  const controller = new AbortController();
  try {
    const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/events`, { headers: { Accept: "text/event-stream" }, signal: controller.signal });
    if (response.ok) return false;
    return (await errorFromResponse(response)).code === "TOO_MANY_STREAMS";
  } finally {
    controller.abort();
  }
}

export function browserWatchDeps(getRun: WatchDeps["getRun"]): WatchDeps {
  return {
    createSource: (url) => new EventSource(url),
    getRun,
    probeStreamLimit,
    setTimer: (callback, ms) => setTimeout(callback, ms),
    clearTimer: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
    backoffMs: defaultBackoffMs,
  };
}
