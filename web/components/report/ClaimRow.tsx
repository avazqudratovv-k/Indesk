import { useTranslations } from "next-intl";
import type { Claim, Evidence } from "@/lib/types";
import { isProven, padNumber, shortLocation, toEvidenceView } from "@/lib/report/view";
import EvidenceChip from "./EvidenceChip";
import EvidencePanel from "./EvidencePanel";
import styles from "./ClaimRow.module.css";

type Props = {
  claim: Claim;
  evidence: Evidence[];
  selectedRef: string | null;
  open: boolean;
  onPick: (ref: string) => void;
};

// One claim: number, text, verified or unverified badge (icon and word), source chips. On phones the open claim shows its
// evidence panel right under the chips.
export default function ClaimRow({ claim, evidence, selectedRef, open, onPick }: Props) {
  const t = useTranslations("report");
  const proven = isProven(claim.status);
  const sources = claim.evidence_refs.flatMap((ref) => {
    const item = evidence.find((candidate) => candidate.ref === ref);
    return item ? [item] : [];
  });
  const opened = open ? sources.find((item) => item.ref === selectedRef) : undefined;

  function label(item: Evidence): string {
    if (item.type === "critic_note") return t("evidence.chip.critic_note");
    const kind = item.type === "passage" ? (shortLocation(item.location) ?? t("evidence.chip.passage")) : t(`evidence.chip.${item.type}`);
    return `${item.ref} · ${kind}`;
  }

  return (
    <li className={`${styles.row} ${proven ? "" : styles.flagged}`}>
      <div className={styles.head}>
        <span className={styles.number}>{padNumber(claim.n)}</span>
        <span className={styles.text}>{claim.text}</span>
        <span className={`${styles.badge} ${proven ? styles.ok : styles.bad}`}>
          {proven ? (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12.5l5 5 9-10" />
            </svg>
          ) : (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" aria-hidden="true">
              <path d="M12 5v9M12 19v.5" />
            </svg>
          )}
          {t(proven ? "detailed.verified" : "detailed.unverified")}
        </span>
      </div>
      <div className={styles.chips}>
        {sources.length > 0 ? (
          sources.map((item) => <EvidenceChip key={item.ref} label={label(item)} selected={selectedRef === item.ref} onClick={() => onPick(item.ref)} />)
        ) : (
          <span className={styles.none}>{t("detailed.noSource")}</span>
        )}
      </div>
      {opened ? <EvidencePanel view={toEvidenceView(opened)} variant="inline" /> : null}
    </li>
  );
}
