import { useFormatter, useTranslations } from "next-intl";
import { formatSize } from "@/lib/workspace/validate";
import { SAMPLE_FILE_BYTES, SAMPLE_FILE_HREF } from "@/lib/workspace/sample";
import styles from "./SampleFile.module.css";

type Props = {
  // Attached: the pending card with ×. Detached: "Use the sample file" and the download link.
  attached: boolean;
  locked: boolean;
  onRemove: () => void;
  onUse: () => void;
};

// The Seoul sample on the Ask tab. It is only pending: nothing is uploaded until Run (see lib/workspace/sample.ts).
export default function SampleFile({ attached, locked, onRemove, onUse }: Props) {
  const t = useTranslations("workspace");
  const format = useFormatter();
  const size = formatSize(SAMPLE_FILE_BYTES);
  return (
    <div className={styles.sample}>
      {attached ? (
        <div className={styles.row}>
          <span className={styles.kind} aria-hidden="true">
            CSV
          </span>
          <span className={styles.info}>
            <span className={styles.name}>{t("sample.title")}</span>
            <span className={styles.meta}>{t("sample.meta", { size: `${format.number(size.value)} ${size.unit}` })}</span>
          </span>
          <button type="button" className={styles.remove} aria-label={t("sample.remove")} disabled={locked} onClick={onRemove}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
      ) : (
        <div className={styles.actions}>
          <button type="button" className={styles.use} disabled={locked} onClick={onUse}>
            {t("sample.use")}
          </button>
          <a className={styles.link} href={SAMPLE_FILE_HREF} download>
            {t("upload.sampleLink")}
          </a>
        </div>
      )}
      <p className={styles.source}>{t("sampleSource")}</p>
    </div>
  );
}
