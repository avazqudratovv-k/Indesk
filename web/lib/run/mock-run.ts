// Scripted demo run for the Workspace run tab (ROADMAP 2.6a). Pure functions over mocks/run-script.json.
// Nothing here reads the user's files or question, and nothing is measured: counts come from the script only.
import { getMockRunScript } from "@/mocks";

export const RUN_AGENTS = ["owl", "chameleon", "beaver", "hound", "cat"] as const;
export type RunAgent = (typeof RUN_AGENTS)[number];

export type RunScenario = "answered" | "partial" | "failed";
export type AgentState = "waiting" | "working" | "done" | "skipped" | "failed";
export type EventKind = "say" | "tool" | "flag";

export type RunEvent = { agent: RunAgent; kind: EventKind; state: Exclude<AgentState, "waiting">; key: string; tok: number; bubble?: "owlSplit" | "owlMerge" };
export type AgentView = { state: AgentState; flags: number };

// Tool-call limit of one run (AGENTS.md: step cap 12).
export const TOOL_CALL_LIMIT = 12;

export function getRunScript(scenario: RunScenario): RunEvent[] {
  return getMockRunScript(scenario);
}

export function isRunScenario(value: unknown): value is RunScenario {
  return value === "answered" || value === "partial" || value === "failed";
}

// State of every agent after the first `step` events. An agent with no event yet is waiting.
export function deriveAgents(events: RunEvent[], step: number): Record<RunAgent, AgentView> {
  const views = Object.fromEntries(RUN_AGENTS.map((id) => [id, { state: "waiting", flags: 0 }])) as Record<RunAgent, AgentView>;
  for (const event of events.slice(0, step)) {
    views[event.agent] = { state: event.state, flags: views[event.agent].flags + (event.kind === "flag" ? 1 : 0) };
  }
  return views;
}

export function countToolCalls(events: RunEvent[], step: number): number {
  return events.slice(0, step).filter((event) => event.kind !== "say").length;
}

export function sumTokens(events: RunEvent[], step: number): number {
  return events.slice(0, step).reduce((sum, event) => sum + event.tok, 0);
}

export function countAgentsDone(agents: Record<RunAgent, AgentView>): number {
  return RUN_AGENTS.filter((id) => agents[id].state === "done").length;
}

// What the team graph draws, from the agents' states (board rules): a connector turns solid when the agent it leads to
// has started (Owl to the three workers) or finished (the three to Cat, Cat to Report); an envelope travels while the
// agent at the end of a connector works, and once from Cat to Report when Cat is done and the report is not yet ready.
export type StageFlow = { edges: boolean[]; envelopes: boolean[] };

export function deriveFlow(agents: Record<RunAgent, AgentView>, reportReady: boolean): StageFlow {
  const working = (id: RunAgent) => agents[id].state === "working";
  const started = (id: RunAgent) => agents[id].state !== "waiting";
  const done = (id: RunAgent) => agents[id].state === "done";
  return {
    edges: [started("chameleon"), started("beaver"), started("hound"), done("chameleon"), done("beaver"), done("hound"), reportReady],
    envelopes: [working("chameleon"), working("beaver"), working("hound"), working("cat"), working("cat"), working("cat"), done("cat") && !reportReady],
  };
}

// The Owl's speech bubble shows only while its newest event carries one; the others show theirs while working.
export function owlBubble(events: RunEvent[], step: number): RunEvent["bubble"] | null {
  const latest = step > 0 ? events[step - 1] : null;
  return latest && latest.agent === "owl" && latest.state === "working" ? (latest.bubble ?? null) : null;
}
