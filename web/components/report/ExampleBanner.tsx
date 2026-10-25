import { useTranslations } from "next-intl";
import styles from "./ExampleBanner.module.css";

// The Report shows scripted sample data, so it says so first (same look as the run tab's demo banner).
export default function ExampleBanner() {
  const t = useTranslations("report.exampleBanner");
  return (
    <p className={styles.banner}>
      <span className={styles.tag}>{t("title")}</span>
      {t("body")}
    </p>
  );
}
