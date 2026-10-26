import { useTranslations } from "next-intl";
import styles from "./ExampleBanner.module.css";

// The example report is a real run on the public Seoul file, so it says so first (same look as the run tab's demo
// banner), with the data source under it.
export default function ExampleBanner() {
  const t = useTranslations("report.exampleBanner");
  return (
    <div className={styles.wrap}>
      <p className={styles.banner}>{t.rich("body", { tag: (chunks) => <span className={styles.tag}>{chunks}</span> })}</p>
      <p className={styles.source}>{t("source")}</p>
    </div>
  );
}
