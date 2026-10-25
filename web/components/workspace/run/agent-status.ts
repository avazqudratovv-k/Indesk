import type { AgentView } from "@/lib/run/mock-run";
import type { RingState } from "./AgentRing";

// A finished agent that raised a flag shows as "flagged"; every other agent shows its own state.
export function ringState(view: AgentView): RingState {
  return view.state === "done" && view.flags > 0 ? "flagged" : view.state;
}

export function statusKey(view: AgentView): "flagged" | AgentView["state"] {
  return view.state === "done" && view.flags > 0 ? "flagged" : view.state;
}
