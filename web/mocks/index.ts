// Typed read functions over web/mocks/*.json (ROADMAP 1.7). Screens call these until the API exists (section 4 swaps them).
import type { RunEvent, RunScenario } from "@/lib/run/mock-run";
import type { Claim, CustomPlanOffer, PlanOffer, Evidence, PersonResult, Report, ShareLink, ShareLinkState, Upload, User } from "@/lib/types";
import claimsFile from "./claims.json";
import evidenceFile from "./evidence.json";
import plansFile from "./plans.json";
import runScriptFile from "./run-script.json";
import reportsFile from "./reports.json";
import shareLinksFile from "./share-links.json";
import uploadsFile from "./uploads.json";
import usersFile from "./users.json";

const planOffers = plansFile.records as PlanOffer[];
const customPlanOffer = plansFile.custom as CustomPlanOffer;
const users = usersFile.records as User[];
const uploads = uploadsFile.records as Upload[];
const reports = reportsFile.records as Report[];
const claims = claimsFile.records as Claim[];
const evidence = evidenceFile.records as Evidence[];
const shareLinks = shareLinksFile.records as ShareLink[];
const shareTokens: Record<string, string> = shareLinksFile.tokens;

// A fixed clock so mock states never flip with real time (sl_01 would expire on 2026-11-01).
export const MOCK_NOW = "2026-10-26T00:00:00Z";

export const MOCK_USER_ID = "u_01";

export function getMockUser(id: string): User | undefined {
  return users.find((user) => user.id === id);
}

export function getMockReport(id: string): Report | undefined {
  return reports.find((report) => report.id === id);
}

export function listMockReports(ownerId: string): Report[] {
  return reports.filter((report) => report.owner_id === ownerId && report.deleted_at === null);
}

export function getMockClaims(reportId: string): Claim[] {
  return claims.filter((claim) => claim.report_id === reportId).sort((a, b) => a.n - b.n);
}

export function getMockEvidence(runId: string): Evidence[] {
  return evidence.filter((item) => item.run_id === runId);
}

export function listMockUploads(userId: string): Upload[] {
  return uploads.filter((upload) => upload.user_id === userId);
}

export function getMockShareLink(reportId: string): ShareLink | undefined {
  return shareLinks.find((link) => link.report_id === reportId);
}

export function getMockShareLinkByToken(token: string): ShareLink | undefined {
  const id = Object.hasOwn(shareTokens, token) ? shareTokens[token] : undefined;
  return shareLinks.find((link) => link.id === id);
}

export function getShareLinkState(link: ShareLink, now: string = MOCK_NOW): ShareLinkState {
  if (link.revoked_at !== null) return "revoked";
  return Date.parse(link.expires_at) <= Date.parse(now) ? "expired" : "active";
}

// People search rules (AGENTS.md): opt-in users only, 2+ characters, max 20 results. Never returns emails.
export function searchMockPeople(query: string): PersonResult[] {
  const needle = query.trim().toLowerCase();
  if (needle.length < 2) return [];
  return users
    .filter((user) => user.discoverable && user.deleted_at === null)
    .filter((user) => user.display_name.toLowerCase().includes(needle) || user.handle.includes(needle))
    .slice(0, 20)
    .map(({ id, display_name, handle }) => ({ id, display_name, handle }));
}

export function listMockDiscoverablePeople(): PersonResult[] {
  return users.filter((user) => user.discoverable).map(({ id, display_name, handle }) => ({ id, display_name, handle }));
}

export function listMockPlanOffers(): PlanOffer[] {
  return planOffers;
}

export function getMockCustomPlanOffer(): CustomPlanOffer {
  return customPlanOffer;
}

// Scripted demo run for the Workspace run tab (ROADMAP 2.6a). Not measured, not from the user's files.
export function getMockRunScript(scenario: RunScenario): RunEvent[] {
  return (runScriptFile.records as Record<RunScenario, RunEvent[]>)[scenario];
}
