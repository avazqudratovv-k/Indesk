import type { Claim, Evidence, Report } from "@/lib/types";
import { getMockClaims, getMockEvidence, getMockReport } from "@/mocks";

// What GET /api/reports/{id} returns (DATA.md section 3): the report, its claims and the evidence its run produced.
export type ReportBundle = { report: Report; claims: Claim[]; evidence: Evidence[] };

// Async on purpose: ROADMAP 4.4 swaps the body for a fetch and nothing else changes.
// Mock phase: any visitor may open a mock report (the example is public, SPEC flow A). The owner check comes with the API.
export async function getReport(id: string): Promise<ReportBundle | null> {
  const report = getMockReport(id);
  if (!report || report.deleted_at !== null) return null;
  return { report, claims: getMockClaims(report.id), evidence: getMockEvidence(report.run_id) };
}
