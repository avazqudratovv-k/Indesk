"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { claimReason, toRealEvidenceView } from "@/lib/report/real/evidence-view";
import { defaultEvidenceRef, toChartView, toEvidenceView } from "@/lib/report/view";
import type { Evidence } from "@/lib/types";
import type { ReportBundle } from "@/lib/report/get-report";
import ClaimList from "./ClaimList";
import ConfidenceCard from "./ConfidenceCard";
import EvidencePanel from "./EvidencePanel";
import ExampleBanner from "./ExampleBanner";
import GrowthChart from "./GrowthChart";
import Glossary from "./Glossary";
import InShortCard from "./InShortCard";
import MeaningCard from "./MeaningCard";
import NextSteps from "./NextSteps";
import { ProseLangProvider } from "./ProseLang";
import ReportPaper from "./ReportPaper";
import ViewToggle, { type ReportViewMode } from "./ViewToggle";
import styles from "./ReportView.module.css";

// What a real report adds to the screen (ROADMAP 4.4): the language its prose is written in (null when unknown) and, when
// that differs from the site language, the language the note names. No `real` prop = the mock example report.
export type RealInfo = { lang: "en" | "ko" | null; note: "en" | "ko" | null };

// The Report (Ask) screen. A mock report (ROADMAP 2.7) says so in the Example banner. A real report (4.4, GET
// /api/reports/{id}) has no banner, no chart and no code: v1 computes neither (DECISIONS #225).
// `example` marks the public example report from GET /api/example: it is real output, so it uses the real views, and it
// keeps the Example banner so nobody takes it for an analysis of their own files.
export default function ReportView({ bundle, real, example = false }: { bundle: ReportBundle; real?: RealInfo; example?: boolean }) {
  const t = useTranslations("report");
  const { report, claims, evidence } = bundle;
  const [view, setView] = useState<ReportViewMode>("simple");
  const summary = report.summary_json;
  const chart = real ? null : toChartView(evidence);
  const say = t as unknown as (key: string, values?: Record<string, string | number>) => string;
  const viewOf = (item: Evidence) => (real ? toRealEvidenceView(item, say) : toEvidenceView(item));
  const [showUnverified, setShowUnverified] = useState(true);
  // The chip that is selected (all chips with that ref light up, as on the board) and, on phones, the claim whose panel is open.
  const [selectedRef, setSelectedRef] = useState<string | null>(() => defaultEvidenceRef(claims, evidence));
  const [openClaim, setOpenClaim] = useState<string | null>(null);
  const selected = evidence.find((item) => item.ref === selectedRef);

  function pick(claimId: string, ref: string) {
    if (selectedRef === ref && openClaim === claimId) {
      setOpenClaim(null);
      return;
    }
    setSelectedRef(ref);
    setOpenClaim(claimId);
  }

  return (
    <ProseLangProvider lang={real?.lang ?? undefined}>
    <main className={styles.main}>
      {real && !example ? null : <ExampleBanner />}
      {real?.note ? <p className={styles.langNote}>{t(`langNote.${real.note}`)}</p> : null}
      <ReportPaper report={report} real={Boolean(real)} />
      <div className={styles.toolbar}>
        <ViewToggle value={view} onChange={setView} />
        <p className={styles.later}>{t("later")}</p>
      </div>
      {claims.length === 0 ? (
        <p className={styles.empty}>{t("states.noClaims")}</p>
      ) : (
        <div className={styles.cols}>
          <article className={styles.article}>
            {view === "simple" && summary.in_short ? <InShortCard items={summary.in_short} /> : null}
            <ConfidenceCard report={report} claims={claims} real={Boolean(real)} />
            {chart ? <GrowthChart chart={chart} /> : null}
            {view === "simple" && summary.meaning ? <MeaningCard text={summary.meaning} /> : null}
            {view === "simple" && summary.next_steps ? <NextSteps steps={summary.next_steps} /> : null}
            {view === "detailed" ? (
              <>
                <ClaimList
                  claims={claims}
                  evidence={evidence}
                  showUnverified={showUnverified}
                  onShowUnverified={setShowUnverified}
                  selectedRef={selectedRef}
                  openClaim={openClaim}
                  onPick={pick}
                  viewOf={viewOf}
                  reasonOf={real ? (claim) => claimReason(claim.evidence_refs, evidence, say) : undefined}
                />
                <Glossary real={Boolean(real)} />
              </>
            ) : null}
          </article>
          {view === "detailed" ? <EvidencePanel view={selected ? viewOf(selected) : null} variant="aside" /> : null}
        </div>
      )}
    </main>
    </ProseLangProvider>
  );
}
