// What each agent produced in the scripted demo run (ROADMAP 2.6b). Pure functions over mocks/run-artifacts.json.
// Items are revealed by the KEY of a run-script event (`after`), never by step count, so the artifacts stay in step
// with the events even if the script is reordered. Nothing here reads the user's files or is measured.
import { getMockRunArtifacts, getMockRunDetail } from "@/mocks";
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

// Shared by all scenarios (see `_detail_note` in the mock). `after` is one event key, or several of which any reveals it.
type After = string | string[];
export type OcrRowRecord = { source: "ocr" | "vision"; text?: string; msg?: string; args?: Record<string, string | number>; conf: string; after: string };
export type PassageTag = "best" | "related" | "context";
export type HoundStepId = "split" | "keyword" | "meaning" | "merge";
export type ArtifactDetail = {
  chameleon: {
    file: string;
    textBox: { left: number; top: number; width: number; height: number; after: string };
    bars: { name: string; value: number }[];
    barBoxesAfter: string;
    valueTagsAfter: string;
    rows: OcrRowRecord[];
  };
  beaver: {
    code: string[];
    codeAfter: string;
    tableAfter: string;
    output: { rows: number; seconds: string; mb: number };
    rows: { station: string; a: string; b: string; growth: number }[];
    highlight: number;
  };
  hound: {
    query: string;
    file: string;
    matched: number;
    steps: { id: HoundStepId; after: After }[];
    searchingAfter: string;
    passagesAfter: string;
    passages: { page: number; tag: PassageTag; pre: string; hl: string; post: string; keyword: number; meaning: number; combined: number }[];
  };
};

export type PassageRecord = ArtifactDetail["hound"]["passages"][number];
export type ChameleonShown = { textBox: ArtifactDetail["chameleon"]["textBox"] | null; barBoxes: boolean; valueTags: boolean; rows: OcrRowRecord[] };
export type BeaverShown = { code: string[] | null; table: ArtifactDetail["beaver"]["rows"] | null };
export type HoundShown = { searching: boolean; steps: { id: HoundStepId; done: boolean }[]; passages: PassageRecord[] | null };

export type ResolvedValue = { number: number } | { text: string } | MsgValue | null;
export type Artifacts = {
  plan: { step: PlanStepId; done: boolean }[];
  questionType: string | null;
  claims: ArtifactClaimRecord[];
  // `value` is null while the agent has not produced it (shown as a dash).
  handover: Record<RunAgent, { label: HandoverLabel; value: ResolvedValue }[]>;
  plannedClaims: number;
  chameleon: ChameleonShown;
  beaver: BeaverShown;
  hound: HoundShown;
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
    ...deriveDetail(seen),
  };
}

// Chameleon, Beaver and Hound reveal by event key too. A list of keys reveals on whichever of them has happened.
function deriveDetail(seen: Set<string>): Pick<Artifacts, "chameleon" | "beaver" | "hound"> {
  const detail = getMockRunDetail();
  const has = (after: After) => (Array.isArray(after) ? after.some((key) => seen.has(key)) : seen.has(after));
  const { chameleon, beaver, hound } = detail;
  return {
    chameleon: {
      textBox: has(chameleon.textBox.after) ? chameleon.textBox : null,
      barBoxes: has(chameleon.barBoxesAfter),
      valueTags: has(chameleon.valueTagsAfter),
      rows: chameleon.rows.filter((row) => has(row.after)),
    },
    beaver: { code: has(beaver.codeAfter) ? beaver.code : null, table: has(beaver.tableAfter) ? beaver.rows : null },
    hound: {
      searching: has(hound.searchingAfter),
      steps: hound.steps.map((step) => ({ id: step.id, done: has(step.after) })),
      passages: has(hound.passagesAfter) ? hound.passages : null,
    },
  };
}
