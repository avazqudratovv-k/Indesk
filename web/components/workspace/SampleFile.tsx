import { useTranslations } from "next-intl";
import styles from "./SampleFile.module.css";

// The public Seoul subway file the example report was made from, so anyone can try Ask without a file of their own.
export const SAMPLE_FILE_HREF = "/demo/seoul_subway_2026-09.csv";

export default function SampleFile() {
  const t = useTranslations("workspace");
  return (
    <div className={styles.sample}>
      <a className={styles.link} href={SAMPLE_FILE_HREF} download>
        {t("upload.sampleLink")}
      </a>
      <p className={styles.source}>{t("sampleSource")}</p>
    </div>
  );
}
