import type { AgentView } from "@/lib/run/mock-run";
import type { RingState } from "./AgentRing";

// A finished agent that raised a flag shows as "flagged"; every other agent shows its own state.
export function ringState(view: AgentView): RingState {
  return view.state === "done" && view.flags > 0 ? "flagged" : view.state;
}

export function statusKey(view: AgentView): "flagged" | AgentView["state"] {
  return view.state === "done" && view.flags > 0 ? "flagged" : view.state;
}

// Once the run is over, an agent that never started can never start: it says "did not run", never "waiting".
export function endedKey(view: AgentView, finished: boolean): "flagged" | AgentView["state"] | "didNotRun" {
  return view.state === "waiting" && finished ? "didNotRun" : statusKey(view);
}

export type TabStatus = "working" | "done" | "flagged" | "waiting" | "failed" | "didNotRun";

// The word and dot of an agent's tab. An agent that never started once the run is over (or was skipped) did not run.
export function tabStatus(view: AgentView, finished: boolean): TabStatus {
  if (view.state === "skipped" || (view.state === "waiting" && finished)) return "didNotRun";
  // "skipped" was handled above, so what is left is one of the tab statuses.
  return statusKey(view) as TabStatus;
}
