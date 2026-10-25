// What each agent produced in the scripted demo run (ROADMAP 2.6b). Pure functions over mocks/run-artifacts.json.
// Items are revealed by the KEY of a run-script event (`after`), never by step count, so the artifacts stay in step
// with the events even if the script is reordered. Nothing here reads the user's files or is measured.
import { getMockRunArtifacts } from "@/mocks";
import { RUN_AGENTS, type RunAgent, type RunEvent, type RunScenario } from "./mock-run";

export type MsgValue = { msg: string; args?: Record<string, string | number> };
export type HandoverValue = { number: number } | { text: string } | MsgValue | { count: "claims" | "verified" | "flagged" } | null;
export type HandoverLabel =
  | "questionType" | "agentsWoken" | "claimsDrafted"
  | "valuesRead" | "readConfidence" | "boxesDrawn"
  | "numbersComputed" | "rowsRead" | "method"
  | "passagesMatched" | "bestMatch" | "pagesSearched"
  | "verified" | "flagged" | "shownWithWarning";
export type PlanStepId = "read" | "classify" | "send" | "merge" | "handToCat";
export type ClaimStatus = "ok" | "unsupported";

export type ArtifactClaimRecord = { n: number; text: { en: string; ko: string }; status: ClaimStatus; reason: MsgValue; evidence: string[]; after: string };
export type ArtifactRecord = {
  plan: { step: PlanStepId; after: string }[];
  questionType: string;
  plannedClaims: number;
  claims: ArtifactClaimRecord[];
  handover: Record<RunAgent, { label: HandoverLabel; value: HandoverValue; after?: string }[]>;
};

export type ResolvedValue = { number: number } | { text: string } | MsgValue | null;
export type Artifacts = {
  plan: { step: PlanStepId; done: boolean }[];
  questionType: string | null;
  claims: ArtifactClaimRecord[];
  // `value` is null while the agent has not produced it (shown as a dash).
  handover: Record<RunAgent, { label: HandoverLabel; value: ResolvedValue }[]>;
  plannedClaims: number;
};

function revealedKeys(events: RunEvent[], step: number): Set<string> {
  return new Set(events.slice(0, step).map((event) => event.key));
}

function resolve(value: HandoverValue, claims: ArtifactClaimRecord[]): ResolvedValue {
  if (value === null) return null;
  if ("count" in value) {
    const count = value.count === "claims" ? claims.length : claims.filter((claim) => (value.count === "verified") === (claim.status === "ok")).length;
    return { number: count };
  }
  return value;
}

export function deriveArtifacts(events: RunEvent[], step: number, scenario: RunScenario): Artifacts {
  const record: ArtifactRecord = getMockRunArtifacts(scenario);
  const seen = revealedKeys(events, step);
  const shown = (after?: string) => after === undefined || seen.has(after);
  return {
    plan: record.plan.map((item) => ({ step: item.step, done: seen.has(item.after) })),
    questionType: seen.has("plan") ? record.questionType : null,
    claims: record.claims.filter((claim) => shown(claim.after)),
    handover: Object.fromEntries(
      RUN_AGENTS.map((agent) => [agent, record.handover[agent].map((row) => ({ label: row.label, value: shown(row.after) ? resolve(row.value, record.claims) : null }))]),
    ) as Artifacts["handover"],
    plannedClaims: record.plannedClaims,
  };
}
