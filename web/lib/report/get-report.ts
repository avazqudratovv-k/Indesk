import { defaultLocale, type Locale } from "@/i18n/config";
import type { Claim, Evidence, Report } from "@/lib/types";
import { localizeClaim, localizeEvidence, localizeReport } from "./localize";
import { getMockClaims, getMockEvidence, getMockReport } from "@/mocks";

// What GET /api/reports/{id} returns (DATA.md section 3): the report, its claims and the evidence its run produced.
export type ReportBundle = { report: Report; claims: Claim[]; evidence: Evidence[] };

// The prose comes back in `locale` and falls back to the original text for any field the translation lacks.
// Async on purpose: ROADMAP 4.4 swaps the body for a fetch and nothing else changes.
// Mock phase: any visitor may open a mock report (the example is public, SPEC flow A). The owner check comes with the API.
export async function getReport(id: string, locale: Locale = defaultLocale): Promise<ReportBundle | null> {
  const report = getMockReport(id);
  if (!report || report.deleted_at !== null) return null;
  return {
    report: localizeReport(report, locale),
    claims: getMockClaims(report.id).map((claim) => localizeClaim(claim, locale)),
    evidence: getMockEvidence(report.run_id).map((item) => localizeEvidence(item, locale)),
  };
}
