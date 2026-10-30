import { describe, expect, it } from "vitest";
import { initialRun, lastSeq, liveReducer, type LiveRun } from "./reducer";
import type { LiveStep, RunSnapshot } from "./types";

function step(seq: number, over: Partial<LiveStep> = {}): LiveStep {
  return { seq, agent: "manager", kind: "say", state: "running", key: "plan", args: {}, tok: 0, bubble: null, ...over };
}

function snapshot(over: Partial<RunSnapshot> = {}): RunSnapshot {
  return { id: "r1", status: "running", outcome: null, reason: null, reportId: null, question: "q", createdAt: 1, startedAt: 2, finishedAt: null, clockOffsetMs: null, steps: [], ...over };
}

function apply(state: LiveRun | null, ...actions: Parameters<typeof liveReducer>[1][]): LiveRun | null {
  return actions.reduce<LiveRun | null>((current, action) => liveReducer(current, action), state);
}

const started = () => apply(null, { type: "start", id: "r1", question: "q", status: "queued", now: 10 }) as LiveRun;

describe("liveReducer", () => {
  it("starts queued with no steps", () => {
    const run = started();
    expect(run.status).toBe("queued");
    expect(run.steps).toEqual([]);
  });

  it("moves to running on the first step and keeps steps in order", () => {
    const run = apply(started(), { type: "step", step: step(2), now: 11 }, { type: "step", step: step(1), now: 12 }, { type: "step", step: step(3), now: 13 }) as LiveRun;
    expect(run.status).toBe("running");
    expect(run.steps.map((s) => s.seq)).toEqual([1, 2, 3]);
    expect(lastSeq(run)).toBe(3);
    expect(run.startedAt).toBe(11);
  });

  it("ignores a step it already has (a replay after a reconnect)", () => {
    const once = apply(started(), { type: "step", step: step(1), now: 1 }, { type: "step", step: step(2), now: 1 }) as LiveRun;
    const again = apply(once, { type: "step", step: step(1), now: 2 }, { type: "step", step: step(2), now: 2 }) as LiveRun;
    expect(again).toBe(once);
  });

  it("resumes from a snapshot, then takes only what is new from the stream", () => {
    const seeded = apply(null, { type: "seed", snapshot: snapshot({ steps: [step(1), step(2)] }) }) as LiveRun;
    expect(seeded.steps).toHaveLength(2);
    const next = apply(seeded, { type: "step", step: step(2), now: 1 }, { type: "step", step: step(3), now: 1 }) as LiveRun;
    expect(next.steps.map((s) => s.seq)).toEqual([1, 2, 3]);
  });

  it("finishes on done and shows the outcome and reason", () => {
    const run = apply(started(), { type: "step", step: step(1), now: 1 }, { type: "done", done: { outcome: "failed", reason: "model_unavailable", reportId: null }, now: 20 }) as LiveRun;
    expect(run.status).toBe("finished");
    expect(run.done).toEqual({ outcome: "failed", reason: "model_unavailable", reportId: null });
    expect(run.finishedAt).toBe(20);
  });

  it("ignores a second done and a step that arrives after done", () => {
    const first = apply(started(), { type: "done", done: { outcome: "answered", reason: null, reportId: null }, now: 5 }) as LiveRun;
    const second = apply(first, { type: "done", done: { outcome: "failed", reason: "internal_error", reportId: null }, now: 6 }) as LiveRun;
    expect(second.done?.outcome).toBe("answered");
    const late = apply(first, { type: "step", step: step(1), now: 7 }) as LiveRun;
    expect(late.status).toBe("finished");
  });

  it("a finished snapshot ends the run, with the reason as a code", () => {
    const run = apply(started(), { type: "seed", snapshot: snapshot({ status: "finished", outcome: "rejected", reason: "daily_cap_user", finishedAt: 9 }) }) as LiveRun;
    expect(run.done).toEqual({ outcome: "rejected", reason: "daily_cap_user", reportId: null });
    expect(run.status).toBe("finished");
  });

  it("an unfinished snapshot never undoes a finished run", () => {
    const finished = apply(started(), { type: "done", done: { outcome: "answered", reason: null, reportId: null }, now: 5 }) as LiveRun;
    const seeded = apply(finished, { type: "seed", snapshot: snapshot({ status: "running" }) }) as LiveRun;
    expect(seeded.done).not.toBeNull();
    expect(seeded.status).toBe("finished");
  });

  it("ignores a snapshot of another run", () => {
    const run = started();
    expect(apply(run, { type: "seed", snapshot: snapshot({ id: "other" }) })).toBe(run);
  });

  it("clear forgets the run", () => {
    expect(apply(started(), { type: "clear" })).toBeNull();
  });

  it("initialRun is queued and empty", () => {
    expect(initialRun("x", "y").steps).toEqual([]);
  });
});
