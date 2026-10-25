import { useTranslations } from "next-intl";
import type { Claim, Evidence } from "@/lib/types";
import { visibleClaims } from "@/lib/report/view";
import ClaimRow from "./ClaimRow";
import styles from "./ClaimList.module.css";

type Props = {
  claims: Claim[];
  evidence: Evidence[];
  showUnverified: boolean;
  onShowUnverified: (next: boolean) => void;
  selectedRef: string | null;
  openClaim: string | null;
  onPick: (claimId: string, ref: string) => void;
};

// Detailed view: every claim with its badge and chips, and a box to hide the ones that are not proven.
// The stamp and the confidence bar keep counting all claims whatever the box says.
export default function ClaimList({ claims, evidence, showUnverified, onShowUnverified, selectedRef, openClaim, onPick }: Props) {
  const t = useTranslations("report.detailed");
  return (
    <section className={styles.section} aria-labelledby="report-claims">
      <div className={styles.head}>
        <h2 id="report-claims" className={styles.title}>
          {t("claimsTitle")}
        </h2>
        <label className={styles.check}>
          <input type="checkbox" className={styles.box} checked={showUnverified} onChange={(event) => onShowUnverified(event.target.checked)} />
          {t("showUnverified")}
        </label>
      </div>
      <ol className={styles.list}>
        {visibleClaims(claims, showUnverified).map((claim) => (
          <ClaimRow key={claim.id} claim={claim} evidence={evidence} selectedRef={selectedRef} open={openClaim === claim.id} onPick={(ref) => onPick(claim.id, ref)} />
        ))}
      </ol>
    </section>
  );
}
