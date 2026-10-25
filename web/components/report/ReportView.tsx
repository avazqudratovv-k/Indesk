"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { defaultEvidenceRef, toChartView, toEvidenceView } from "@/lib/report/view";
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
import ReportPaper from "./ReportPaper";
import ViewToggle, { type ReportViewMode } from "./ViewToggle";
import styles from "./ReportView.module.css";

// The Report (Ask) screen, ROADMAP 2.7. Every record is mock data (the page says so in the Example banner); ROADMAP 4.4
// swaps getReport() for the API and this component does not change.
export default function ReportView({ bundle }: { bundle: ReportBundle }) {
  const t = useTranslations("report");
  const { report, claims, evidence } = bundle;
  const [view, setView] = useState<ReportViewMode>("simple");
  const summary = report.summary_json;
  const chart = toChartView(evidence);
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
    <main className={styles.main}>
      <ExampleBanner />
      <ReportPaper report={report} />
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
            <ConfidenceCard report={report} claims={claims} />
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
                />
                <Glossary />
              </>
            ) : null}
          </article>
          {view === "detailed" ? <EvidencePanel view={selected ? toEvidenceView(selected) : null} variant="aside" /> : null}
        </div>
      )}
    </main>
  );
}
