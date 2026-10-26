import type { AgentView, RunAgent } from "@/lib/run/mock-run";
import { agentBuilt } from "@/components/home/agents";
import type { RingState } from "./AgentRing";

// A finished agent that raised a flag shows as "flagged"; every other agent shows its own state.
export function ringState(view: AgentView): RingState {
  return view.state === "done" && view.flags > 0 ? "flagged" : view.state;
}

export function statusKey(view: AgentView): "flagged" | AgentView["state"] {
  return view.state === "done" && view.flags > 0 ? "flagged" : view.state;
}

// Once the run is over, an agent that never started can never start: it says "did not run", never "waiting".
export function endedKey(id: RunAgent, view: AgentView, finished: boolean, real = false): "flagged" | AgentView["state"] | "didNotRun" | "comingLater" {
  if (isComingLater(id, view, real)) return "comingLater";
  return view.state === "waiting" && finished ? "didNotRun" : statusKey(view);
}

// Real runs only: an agent that is not built yet (Chameleon, Hound) is "Coming later", never "Did not run" or "Skipped".
// A built agent keeps its real state. The mock run keeps its scripted states.
export function isComingLater(id: RunAgent, view: AgentView, real: boolean): boolean {
  return real && !agentBuilt[id] && (view.state === "skipped" || view.state === "waiting");
}

export type TabStatus = "working" | "done" | "flagged" | "waiting" | "failed" | "didNotRun" | "comingLater";

// The word and dot of an agent's tab. An agent that never started once the run is over (or was skipped) did not run.
export function tabStatus(id: RunAgent, view: AgentView, finished: boolean, real = false): TabStatus {
  if (isComingLater(id, view, real)) return "comingLater";
  if (view.state === "skipped" || (view.state === "waiting" && finished)) return "didNotRun";
  // "skipped" was handled above, so what is left is one of the tab statuses.
  return statusKey(view) as TabStatus;
}
