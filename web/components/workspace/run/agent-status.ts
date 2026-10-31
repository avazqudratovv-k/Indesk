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
export function endedKey(id: RunAgent, view: AgentView, finished: boolean, real = false): "flagged" | AgentView["state"] | "didNotRun" | "comingLater" | "notUsed" {
  if (isComingLater(id, view, real)) return "comingLater";
  if (isNotUsed(id, view, real)) return "notUsed";
  return view.state === "waiting" && finished ? "didNotRun" : statusKey(view);
}

// Real runs only: an agent that is not built yet (Chameleon) is "Not available yet", never "Did not run" or "Skipped".
// A built agent keeps its real state. The mock run keeps its scripted states.
export function isComingLater(id: RunAgent, view: AgentView, real: boolean): boolean {
  return real && !agentBuilt[id] && (view.state === "skipped" || view.state === "waiting");
}

// Real runs only: Hound works on PDFs and Beaver on CSVs, so each is skipped in the other kind of run. That agent is
// "not used", a neutral word. An agent that is still waiting when the run ends never started: that is "did not start"
// (a run that failed early), not "not used", because the run kind may not be known yet.
export function isNotUsed(id: RunAgent, view: AgentView, real: boolean): boolean {
  if (!real) return false;
  return (id === "hound" || id === "beaver") && view.state === "skipped";
}

export type RunKind = "csv" | "pdf";

// The agents that can work in each kind of run; "Agents done N / M" counts only these.
export const RUN_WORKERS: Record<RunKind, readonly RunAgent[]> = { csv: ["owl", "beaver", "cat"], pdf: ["owl", "hound", "cat"] };

// The kind of a real run, read from its events: Hound working (or Beaver skipped) is a PDF run, Beaver working (or Hound
// skipped) is a CSV run. Null while neither worker has started.
export function runKind(agents: Record<RunAgent, AgentView>): RunKind | null {
  const started = (view: AgentView) => view.state !== "waiting" && view.state !== "skipped";
  if (started(agents.hound) || agents.beaver.state === "skipped") return "pdf";
  if (started(agents.beaver) || agents.hound.state === "skipped") return "csv";
  return null;
}

// In a PDF run Beaver is not used from the moment the run is known to be a PDF run: its waiting state becomes skipped.
export function markUnused(agents: Record<RunAgent, AgentView>, kind: RunKind | null): Record<RunAgent, AgentView> {
  if (kind !== "pdf" || agents.beaver.state !== "waiting") return agents;
  return { ...agents, beaver: { ...agents.beaver, state: "skipped" } };
}

export type TabStatus = "working" | "done" | "flagged" | "waiting" | "failed" | "didNotRun" | "comingLater" | "notUsed";

// The word and dot of an agent's tab. An agent that never started once the run is over (or was skipped) did not run.
export function tabStatus(id: RunAgent, view: AgentView, finished: boolean, real = false): TabStatus {
  if (isComingLater(id, view, real)) return "comingLater";
  if (isNotUsed(id, view, real)) return "notUsed";
  if (view.state === "skipped" || (view.state === "waiting" && finished)) return "didNotRun";
  // "skipped" was handled above, so what is left is one of the tab statuses.
  return statusKey(view) as TabStatus;
}
