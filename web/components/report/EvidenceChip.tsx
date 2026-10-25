import styles from "./EvidenceChip.module.css";

// A source chip under a claim. Selected chips fill with the accent colour (`aria-pressed`).
export default function EvidenceChip({ label, selected, onClick }: { label: string; selected: boolean; onClick: () => void }) {
  return (
    <button type="button" className={styles.chip} aria-pressed={selected} onClick={onClick}>
      {label}
    </button>
  );
}
