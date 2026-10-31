import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/errors";
import { watchRun, type SourceLike, type WatchDeps, type WatchHandlers } from "./watch";
import type { RunSnapshot } from "./types";

type Listener = (event: MessageEvent | Event) => void;

class FakeSource implements SourceLike {
  readyState = 0;
  closed = false;
  listeners = new Map<string, Listener[]>();
  constructor(readonly url: string) {}
  addEventListener(type: string, listener: Listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }
  emit(type: string, data?: unknown) {
    for (const listener of this.listeners.get(type) ?? []) listener(data === undefined ? new Event(type) : new MessageEvent(type, { data: JSON.stringify(data) }));
  }
  open() {
    this.readyState = 1;
    this.emit("open");
  }
  // The browser is retrying by itself.
  dropWhileRetrying() {
    this.readyState = 0;
    this.emit("error");
  }
  // The browser gave up (an HTTP error, or the 204 for a run that is over).
  giveUp() {
    this.readyState = 2;
    this.emit("error");
  }
}

const RUN = "123e4567-e89b-12d3-a456-426614174000";
const stepData = (seq: number) => ({ seq, agent: "manager", kind: "say", state: "running", key: "plan", args: {}, tok: 0, bubble: null });
const snap = (over: Partial<RunSnapshot> = {}): RunSnapshot => ({ id: RUN, status: "running", outcome: null, reason: null, reportId: null, question: "q", createdAt: null, startedAt: null, finishedAt: null, clockOffsetMs: null, steps: [], ...over });

function setup(getRun: WatchDeps["getRun"] = async () => snap()) {
  const sources: FakeSource[] = [];
  const deps: WatchDeps = {
    createSource: (url) => {
      const source = new FakeSource(url);
      sources.push(source);
      return source;
    },
    getRun: vi.fn(getRun),
    setTimer: (callback, ms) => setTimeout(callback, ms),
    clearTimer: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
    backoffMs: [1000, 2000, 4000],
  };
  const handlers = { onStep: vi.fn(), onDone: vi.fn(), onSnapshot: vi.fn(), onGone: vi.fn(), onLost: vi.fn() } satisfies WatchHandlers;
  return { sources, deps, handlers };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("watchRun", () => {
  it("opens the same-origin event URL", () => {
    const t = setup();
    const w = watchRun(RUN, t.handlers, t.deps);
    expect(t.sources[0].url).toBe(`/api/runs/${RUN}/events`);
    w.close();
  });

  it("passes steps on and finishes on done, closing the stream", () => {
    const t = setup();
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].open();
    t.sources[0].emit("step", stepData(1));
    t.sources[0].emit("done", { outcome: "answered", reason: null, report_id: null });
    expect(t.handlers.onStep).toHaveBeenCalledTimes(1);
    expect(t.handlers.onDone).toHaveBeenCalledWith({ outcome: "answered", reason: null, reportId: null });
    expect(t.sources[0].closed).toBe(true);
  });

  it("drops a step that does not fit the shape", () => {
    const t = setup();
    const w = watchRun(RUN, t.handlers, t.deps);
    t.sources[0].emit("step", { seq: 1, agent: "dog" });
    expect(t.handlers.onStep).not.toHaveBeenCalled();
    w.close();
  });

  it("an unreadable done is a failure, never a success", () => {
    const t = setup();
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].emit("done", { outcome: "great" });
    expect(t.handlers.onDone).toHaveBeenCalledWith({ outcome: "failed", reason: null, reportId: null });
  });

  it("leaves the browser's own reconnect alone for a single drop", async () => {
    const t = setup();
    const w = watchRun(RUN, t.handlers, t.deps);
    t.sources[0].dropWhileRetrying();
    await vi.runAllTimersAsync();
    expect(t.deps.getRun).not.toHaveBeenCalled();
    expect(t.sources).toHaveLength(1);
    t.sources[0].open(); // the browser reconnected (and sent Last-Event-ID)
    t.sources[0].dropWhileRetrying();
    expect(t.deps.getRun).not.toHaveBeenCalled();
    w.close();
  });

  it("after repeated drops asks GET /api/runs/{id}, then reopens once with backoff", async () => {
    const t = setup();
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].dropWhileRetrying();
    t.sources[0].dropWhileRetrying();
    await vi.advanceTimersByTimeAsync(0);
    expect(t.deps.getRun).toHaveBeenCalledTimes(1);
    expect(t.handlers.onSnapshot).toHaveBeenCalled();
    expect(t.sources[0].closed).toBe(true);
    expect(t.sources).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(t.sources).toHaveLength(2);
  });

  it("a 204 (the browser closes the stream) on a finished run ends with done and no reopen", async () => {
    const t = setup(async () => snap({ status: "finished", outcome: "answered", steps: [] }));
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].giveUp();
    await vi.advanceTimersByTimeAsync(0);
    expect(t.handlers.onDone).toHaveBeenCalledWith({ outcome: "answered", reason: null, reportId: null });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(t.sources).toHaveLength(1);
  });

  it("a finished failed run is shown with its reason", async () => {
    const t = setup(async () => snap({ status: "finished", outcome: "rejected", reason: "daily_cap_user" }));
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].giveUp();
    await vi.advanceTimersByTimeAsync(0);
    expect(t.handlers.onDone).toHaveBeenCalledWith({ outcome: "rejected", reason: "daily_cap_user", reportId: null });
  });

  it("never loops: after the cap it reports the connection as lost", async () => {
    const t = setup();
    watchRun(RUN, t.handlers, t.deps);
    for (let i = 0; i < 10; i += 1) {
      const current = t.sources[t.sources.length - 1];
      if (!current.closed) current.giveUp();
      await vi.advanceTimersByTimeAsync(20_000);
    }
    expect(t.sources).toHaveLength(1 + t.deps.backoffMs.length);
    expect(t.handlers.onLost).toHaveBeenCalledTimes(1);
    expect(t.handlers.onLost).toHaveBeenCalledWith({ signedOut: false });
    expect(t.deps.getRun).toHaveBeenCalledTimes(1 + t.deps.backoffMs.length);
  });

  it("a signed-out answer stops at once and says so", async () => {
    const t = setup(async () => {
      throw new ApiError(401, "UNAUTHENTICATED");
    });
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].giveUp();
    await vi.advanceTimersByTimeAsync(0);
    expect(t.handlers.onLost).toHaveBeenCalledWith({ signedOut: true });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(t.sources).toHaveLength(1);
  });

  it("a run that is not found is reported gone and not retried", async () => {
    const t = setup(async () => {
      throw new ApiError(404, "NOT_FOUND");
    });
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].giveUp();
    await vi.advanceTimersByTimeAsync(0);
    expect(t.handlers.onGone).toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(t.sources).toHaveLength(1);
  });

  it("treats a network failure of the check like a run that is still going", async () => {
    const t = setup(async () => {
      throw new ApiError(0, "NETWORK");
    });
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].giveUp();
    await vi.advanceTimersByTimeAsync(1000);
    expect(t.sources).toHaveLength(2);
  });

  it("close() stops everything, including a pending reopen", async () => {
    const t = setup();
    const w = watchRun(RUN, t.handlers, t.deps);
    t.sources[0].giveUp();
    await vi.advanceTimersByTimeAsync(0);
    w.close();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(t.sources).toHaveLength(1);
  });

  it("ignores events from a stream it already closed", () => {
    const t = setup();
    const w = watchRun(RUN, t.handlers, t.deps);
    const old = t.sources[0];
    w.close();
    old.emit("step", stepData(1));
    expect(t.handlers.onStep).not.toHaveBeenCalled();
  });

  it("never leaves two streams for the same run (StrictMode runs the effect twice)", () => {
    const t = setup();
    watchRun(RUN, t.handlers, t.deps);
    const second = watchRun(RUN, t.handlers, t.deps);
    expect(t.sources).toHaveLength(2);
    expect(t.sources[0].closed).toBe(true);
    expect(t.sources[1].closed).toBe(false);
    second.close();
  });
});

describe("stream limit", () => {
  it("says so when the server refuses because too many streams are open", async () => {
    const t = setup();
    t.deps.probeStreamLimit = vi.fn(async () => true);
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].giveUp();
    await vi.advanceTimersByTimeAsync(0);
    expect(t.handlers.onLost).toHaveBeenCalledWith({ signedOut: false, tooManyStreams: true });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(t.sources).toHaveLength(1);
  });

  it("keeps retrying as before when the probe finds no limit", async () => {
    const t = setup();
    t.deps.probeStreamLimit = vi.fn(async () => false);
    watchRun(RUN, t.handlers, t.deps);
    t.sources[0].giveUp();
    await vi.advanceTimersByTimeAsync(1500);
    expect(t.handlers.onLost).not.toHaveBeenCalled();
    expect(t.sources).toHaveLength(2);
  });
});
