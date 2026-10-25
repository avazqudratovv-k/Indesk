import Link from "next/link";
import { useTranslations } from "next-intl";
import { workspaceHref } from "./agents";
import section from "./HomeSection.module.css";
import styles from "./HomeClosing.module.css";

export default function HomeClosing() {
  const t = useTranslations("home.closing");
  return (
    <section className={`${section.section} ${styles.wrap}`} aria-labelledby="closing-title">
      <div className={`dk ${styles.band}`}>
        <div className={styles.text}>
          <h2 id="closing-title" className={styles.title}>
            {t("title")}
          </h2>
          <p className={styles.body}>{t("body")}</p>
        </div>
        <div className={styles.actions}>
          <Link className={styles.primary} href={workspaceHref}>
            {t("tryDemo")}
          </Link>
          <Link className={styles.secondary} href="/plans">
            {t("seePlans")}
          </Link>
        </div>
      </div>
    </section>
  );
}
