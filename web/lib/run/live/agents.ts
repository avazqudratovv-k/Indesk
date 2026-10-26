import type { AgentState, RunAgent, RunEvent } from "@/lib/run/mock-run";
import type { BackendAgent, BackendStepState, LiveStep } from "./types";

// Backend agent ids to the UI's animals (api/app/core/enums.py AgentKey).
export const AGENT_MAP: Record<BackendAgent, RunAgent> = { manager: "owl", vision: "chameleon", data: "beaver", retrieval: "hound", critic: "cat" };

// Backend step states to what the components draw. `queued` has no UI state (the agent has not started), so a queued
// line is not drawn; `timed_out` is a failure for the person looking at it.
export const STATE_MAP: Record<BackendStepState, Exclude<AgentState, "waiting"> | null> = {
  queued: null,
  running: "working",
  done: "done",
  skipped: "skipped",
  failed: "failed",
  timed_out: "failed",
};

// Steps to the events the existing run components take. `describe` returns the translated line for a step.
export function toRunEvents(steps: readonly LiveStep[], describe: (step: LiveStep) => string): RunEvent[] {
  const events: RunEvent[] = [];
  for (const step of steps) {
    const state = STATE_MAP[step.state];
    if (!state) continue;
    events.push({ agent: AGENT_MAP[step.agent], kind: step.kind, state, key: step.key, tok: step.tok, bubble: step.bubble ?? undefined, text: describe(step) });
  }
  return events;
}

export function isSimulated(steps: readonly LiveStep[]): boolean {
  return steps.some((step) => step.args.stub === true);
}
